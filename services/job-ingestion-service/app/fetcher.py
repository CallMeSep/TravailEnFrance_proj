from __future__ import annotations

import ast
import json
import logging
import os
import time
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.data_pipeline.extraction.extraction import get_job_list, job_search

logger = logging.getLogger(__name__)


# --- extract / envelope -----------------------------------------------------


def _jobs_from_payload(payload: Any) -> list[dict[str, Any]]:
    """Match France Travail (`resultats`) and other common API envelope shapes."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        resultats = payload.get("resultats")
        if isinstance(resultats, list):
            return [x for x in resultats if isinstance(x, dict)]
        for key in ("results", "items", "jobs", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def _keywords_from_env(raw: str) -> str | list[str] | None:
    """Parse JOB_SEARCH_KEYWORDS: JSON list or comma-separated (same rules as job_search)."""
    raw = raw.strip()
    if not raw:
        return None
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, list):
            cleaned = [str(k).strip() for k in parsed if len(str(k).strip()) >= 2][:7]
            return cleaned or None
        return None
    parts = [p.strip() for p in raw.split(",") if len(p.strip()) >= 2][:7]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return parts


def _crawl_jobs_by_tech(
    technologies: list[str],
    contract_type: str,
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    """
    Replicates old script flow:
    - loop over technologies
    - call job_search("stage,<tech>") (or only "stage" when tech is empty)
    - sleep between API calls for rate limiting
    """
    sleep_seconds = float(os.getenv("FETCH_SLEEP_SECONDS", "2"))
    logger.info("Starting crawl for %s technologies", len(technologies))

    all_jobs: list[dict[str, Any]] = []
    for i, tech in enumerate(technologies):
        tech = (tech or "").strip()
        contract = (contract_type or "").strip()
        if contract and tech:
            query = f"{contract},{tech}"
        elif contract:
            query = contract
        else:
            query = tech

        if not query:
            continue

        logger.info("--- Crawling jobs for: %s ---", tech or "<empty>")
        payload = job_search(query, timeout_seconds=timeout_seconds)
        jobs = _jobs_from_payload(payload)
        if jobs:
            all_jobs.extend(jobs)
        else:
            logger.info("No results found for %s", tech or "<empty>")

        # Preserve old behavior to avoid hitting rate limits.
        if i < len(technologies) - 1 and sleep_seconds > 0:
            time.sleep(sleep_seconds)

    logger.info("Crawl complete. Total jobs fetched: %s", len(all_jobs))
    return all_jobs


def fetch_jobs_from_external_api(
    *,
    technologies: list[str] | None = None,
    contract_type: str | None = None,
    search_terms: str | list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    OAuth client credentials, Bearer + Accept headers, France Travail search
    or configured list URL (same as `data_pipeline/extraction`).
    """
    timeout_seconds = float(os.getenv("FETCH_TIMEOUT_SECONDS", "20"))
    keywords_env = os.getenv("JOB_SEARCH_KEYWORDS", "").strip()

    if technologies is not None or contract_type:
        tech_values = technologies if technologies is not None else [""]
        return _crawl_jobs_by_tech(
            technologies=tech_values,
            contract_type=contract_type or "",
            timeout_seconds=timeout_seconds,
        )

    if search_terms:
        payload = job_search(search_terms, timeout_seconds=timeout_seconds)
    elif keywords_env:
        spec = _keywords_from_env(keywords_env)
        payload = job_search(spec or "", timeout_seconds=timeout_seconds)
    else:
        payload = get_job_list(timeout_seconds=timeout_seconds)

    return _jobs_from_payload(payload)


# --- transform (aligned with data_pipeline/transformation/transform_data) ---


def _normalize_lieu_travail(val: Any) -> dict[str, Any]:
    """Same behaviour as `extract_lieu_travail_detailed` without pandas."""
    default = {
        "libelle": "",
        "latitude": None,
        "longitude": None,
        "codePostal": "",
        "commune": "",
    }
    if val is None or val == "" or val == "{}":
        return dict(default)
    try:
        lieu = json.loads(val.replace("'", '"')) if isinstance(val, str) else val
        if not isinstance(lieu, dict):
            return dict(default)
        return {
            "libelle": lieu.get("libelle", ""),
            "latitude": lieu.get("latitude"),
            "longitude": lieu.get("longitude"),
            "codePostal": lieu.get("codePostal", ""),
            "commune": lieu.get("commune", ""),
        }
    except Exception:
        return dict(default)


def _normalize_entreprise(val: Any) -> dict[str, Any]:
    """Same behaviour as `extract_entreprise_info` without pandas."""
    default = {"nom": "", "description": "", "entrepriseAdaptee": ""}
    if val is None or val == "" or val == "{}":
        return dict(default)
    try:
        societe = ast.literal_eval(val) if isinstance(val, str) else val
        if not isinstance(societe, dict):
            return dict(default)
        return {
            "nom": societe.get("nom", ""),
            "description": societe.get("description", ""),
            "entrepriseAdaptee": str(societe.get("entrepriseAdaptee", "")),
        }
    except Exception:
        return dict(default)


def transform_job(job: dict[str, Any]) -> dict[str, Any]:
    """Apply lieu + entreprise normalization; leaves other keys unchanged."""
    return {
        **job,
        "lieuTravail": _normalize_lieu_travail(job.get("lieuTravail")),
        "entreprise": _normalize_entreprise(job.get("entreprise")),
    }


def transform_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [transform_job(j) for j in jobs]


# --- load (Postgres `jobs` upsert) -----------------------------------------


def _coerce_mapping(value: Any) -> dict[str, Any]:
    """Fallback if nested fields are still string-encoded."""
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    if isinstance(value, str):
        s = value.strip()
        if not s or s == "{}":
            return {}
        try:
            if s.startswith("{") and "'" in s:
                parsed = ast.literal_eval(s)
                return parsed if isinstance(parsed, dict) else {}
            return json.loads(s.replace("'", '"'))
        except (ValueError, SyntaxError, json.JSONDecodeError):
            return {}
    return {}


def _normalize_salaire(value: Any) -> Any:
    """
    DB column expects a scalar; API sometimes sends `salaire` as object.
    Keep scalar values as-is, and serialize objects/lists to JSON text.
    """
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _parse_datetime(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def upsert_job(
    db: Session,
    job: dict[str, Any],
    *,
    raw_job: dict[str, Any] | None = None,
) -> None:
    sql = text(
        """
        INSERT INTO jobs (
          id, intitule, description, date_creation, date_actualisation, lieu_travail,
          rome_code, entreprise_nom, type_contrat, type_contrat_libelle,
          nature_contrat, experience_exige, experience_libelle,
          salaire, alternance, qualification_code,
          qualification_libelle, code_naf, secteur_activite, secteur_activite_libelle,
          latitude, longitude, commune, raw_data, updated_at
        ) VALUES (
          :id, :intitule, :description, :date_creation, :date_actualisation, :lieu_travail,
          :rome_code, :entreprise_nom, :type_contrat, :type_contrat_libelle,
          :nature_contrat, :experience_exige, :experience_libelle,
          :salaire, :alternance, :qualification_code,
          :qualification_libelle, :code_naf, :secteur_activite, :secteur_activite_libelle,
          :latitude, :longitude, :commune, CAST(:raw_data AS JSONB), NOW()
        )
        ON CONFLICT (id) DO UPDATE SET
          intitule = EXCLUDED.intitule,
          description = EXCLUDED.description,
          date_creation = EXCLUDED.date_creation,
          date_actualisation = EXCLUDED.date_actualisation,
          lieu_travail = EXCLUDED.lieu_travail,
          rome_code = EXCLUDED.rome_code,
          entreprise_nom = EXCLUDED.entreprise_nom,
          type_contrat = EXCLUDED.type_contrat,
          type_contrat_libelle = EXCLUDED.type_contrat_libelle,
          nature_contrat = EXCLUDED.nature_contrat,
          experience_exige = EXCLUDED.experience_exige,
          experience_libelle = EXCLUDED.experience_libelle,
          salaire = EXCLUDED.salaire,
          alternance = EXCLUDED.alternance,
          qualification_code = EXCLUDED.qualification_code,
          qualification_libelle = EXCLUDED.qualification_libelle,
          code_naf = EXCLUDED.code_naf,
          secteur_activite = EXCLUDED.secteur_activite,
          secteur_activite_libelle = EXCLUDED.secteur_activite_libelle,
          latitude = EXCLUDED.latitude,
          longitude = EXCLUDED.longitude,
          commune = EXCLUDED.commune,
          raw_data = EXCLUDED.raw_data,
          updated_at = NOW()
        """
    )

    location = _coerce_mapping(job.get("lieuTravail"))
    enterprise = _coerce_mapping(job.get("entreprise"))
    raw_source = raw_job if raw_job is not None else job

    params = {
        "id": str(job.get("id", "")),
        "intitule": job.get("intitule"),
        "description": job.get("description"),
        "date_creation": _parse_datetime(job.get("dateCreation")),
        "date_actualisation": _parse_datetime(job.get("dateActualisation")),
        "lieu_travail": location.get("libelle") or job.get("libelle"),
        "rome_code": job.get("romeCode"),
        "entreprise_nom": enterprise.get("nom") or job.get("entreprise_nom"),
        "type_contrat": job.get("typeContrat"),
        "type_contrat_libelle": job.get("typeContratLibelle"),
        "nature_contrat": job.get("natureContrat"),
        "experience_exige": job.get("experienceExige"),
        "experience_libelle": job.get("experienceLibelle"),
        "salaire": _normalize_salaire(job.get("salaire")),
        "alternance": job.get("alternance"),
        "qualification_code": job.get("qualificationCode"),
        "qualification_libelle": job.get("qualificationLibelle"),
        "code_naf": job.get("codeNAF"),
        "secteur_activite": job.get("secteurActivite"),
        "secteur_activite_libelle": job.get("secteurActiviteLibelle"),
        "latitude": location.get("latitude") or job.get("latitude"),
        "longitude": location.get("longitude") or job.get("longitude"),
        "commune": location.get("commune") or job.get("commune"),
        "raw_data": json.dumps(raw_source),
    }

    if not params["id"]:
        return

    db.execute(sql, params)


def load_jobs(db: Session, jobs: list[dict[str, Any]], *, raw_jobs: list[dict[str, Any]] | None = None) -> int:
    """
    Transform each record then upsert. If `raw_jobs` is provided (same length as `jobs`),
    `raw_data` stores the untransformed payload; otherwise `jobs` is used for `raw_data`.
    """
    if raw_jobs is not None and len(raw_jobs) != len(jobs):
        raise ValueError("raw_jobs must be the same length as jobs")

    upserted = 0
    for i, job in enumerate(jobs):
        raw = raw_jobs[i] if raw_jobs is not None else None
        upsert_job(db, job, raw_job=raw)
        upserted += 1
    return upserted


def fetch_process_and_load(
    db: Session,
    *,
    technologies: list[str] | None = None,
    contract_type: str | None = None,
    search_terms: str | list[str] | None = None,
) -> tuple[int, int]:
    """
    Full pipeline: fetch from API → transform (lieu / entreprise) → upsert into `jobs`.
    Does not commit; caller owns the transaction.
    Returns (fetched_count, upsert_attempt_count).
    """
    raw_jobs = fetch_jobs_from_external_api(
        technologies=technologies,
        contract_type=contract_type,
        search_terms=search_terms,
    )
    transformed = [transform_job(j) for j in raw_jobs]
    n = load_jobs(db, transformed, raw_jobs=raw_jobs)
    return len(raw_jobs), n
