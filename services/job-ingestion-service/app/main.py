from __future__ import annotations

import os
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import text

from .database import SessionLocal
from .fetcher import fetch_process_and_load

app = FastAPI(title="Job Ingestion Service", version="1.0.0")
scheduler = BackgroundScheduler(timezone="UTC")
last_run: dict[str, str | int | None] = {
    "status": "never",
    "fetched": 0,
    "upserted": 0,
    "error": None,
    "at": None,
}


class RunNowRequest(BaseModel):
    search_terms: str | None = None


def run_ingestion(*, search_terms: str | None = None):
    global last_run
    db = SessionLocal()
    try:
        fetched, upserted = fetch_process_and_load(db, search_terms=search_terms)
        db.commit()
        last_run = {
            "status": "ok",
            "fetched": fetched,
            "upserted": upserted,
            "error": None,
            "at": datetime.utcnow().isoformat(),
        }
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        last_run = {
            "status": "error",
            "fetched": 0,
            "upserted": 0,
            "error": str(exc),
            "at": datetime.utcnow().isoformat(),
        }
    finally:
        db.close()


def _cleanup_unused_columns():
    """
    Drop legacy/unused columns that are always empty in current pipeline.
    Safe to rerun because each DROP uses IF EXISTS.
    """
    columns_to_drop = [
        "rome_libelle",
        "appellation_libelle",
        "duree_travail_libelle",
        "duree_travail_libelle_converti",
        "nombre_postes",
        "code_postal",
        # Defensive: if old schema used non-snake-case names
        "romelibelle",
        "appellationlibelle",
        "dureetravaillibelle",
        "dureetravaillibelleconverti",
        "nombrepostes",
        "codepostal",
    ]
    db = SessionLocal()
    try:
        for col in columns_to_drop:
            db.execute(text(f"ALTER TABLE IF EXISTS jobs DROP COLUMN IF EXISTS {col}"))
        db.commit()
    finally:
        db.close()


def _ensure_required_columns():
    """Add back required timestamp columns if they were removed earlier."""
    db = SessionLocal()
    try:
        db.execute(text("ALTER TABLE IF EXISTS jobs ADD COLUMN IF NOT EXISTS date_creation TIMESTAMP NULL"))
        db.execute(text("ALTER TABLE IF EXISTS jobs ADD COLUMN IF NOT EXISTS date_actualisation TIMESTAMP NULL"))
        db.execute(text("ALTER TABLE IF EXISTS jobs ADD COLUMN IF NOT EXISTS type_contrat TEXT"))
        db.execute(text("ALTER TABLE IF EXISTS jobs ADD COLUMN IF NOT EXISTS type_contrat_libelle TEXT"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_jobs_date_actualisation ON jobs (date_actualisation)"))
        db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    _ensure_required_columns()
    _cleanup_unused_columns()
    cron_schedule = os.getenv("CRON_SCHEDULE", "0 2 * * *")
    minute, hour, day, month, day_of_week = cron_schedule.split()
    scheduler.add_job(
        run_ingestion,
        trigger="cron",
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
    )
    scheduler.start()

    if os.getenv("RUN_ON_STARTUP", "true").lower() == "true":
        run_ingestion()


@app.on_event("shutdown")
def on_shutdown():
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/health")
def health_check():
    return {"status": "ok", "last_run": last_run}


@app.post("/run-now")
def run_now(payload: RunNowRequest | None = None):
    run_ingestion(search_terms=payload.search_terms if payload else None)
    return {"status": "triggered", "last_run": last_run}
