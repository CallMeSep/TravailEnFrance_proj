import hashlib
import os
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Favorite, Job, Skill, User
from .schemas import AuthResponse, FavoriteJobIdsResponse, JobDetail, JobListItem, LoginRequest, RegisterRequest, UserPublic

app = FastAPI(title="Job API Service", version="1.0.0")
PASSWORD_SALT = os.getenv("PASSWORD_SALT", "change-this-salt")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


def _hash_password(password: str) -> str:
    return hashlib.sha256(f"{PASSWORD_SALT}:{password}".encode("utf-8")).hexdigest()


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/jobs", response_model=list[JobListItem])
def list_jobs(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    title: str | None = Query(default=None),
    commune: str | None = Query(default=None),
    type_contrat: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Job)

    if title:
        query = query.filter(Job.intitule.ilike(f"%{title.strip()}%"))
    if commune:
        query = query.filter(Job.commune.ilike(f"%{commune.strip()}%"))
    if type_contrat:
        contract_filter = f"%{type_contrat.strip()}%"
        query = query.filter(
            or_(
                Job.type_contrat.ilike(contract_filter),
                Job.type_contrat_libelle.ilike(contract_filter),
            )
        )
    jobs = query.order_by(desc(Job.date_actualisation).nullslast(), Job.id).offset(offset).limit(limit).all()
    return jobs


@app.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/auth/register", response_model=AuthResponse)
def register_user(payload: RegisterRequest, db: Session = Depends(get_db)):
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    try:
        dob = datetime.strptime(payload.dob, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid DOB format. Use YYYY-MM-DD") from exc

    user = User(
        username=username,
        password_hash=_hash_password(payload.password),
        dob=dob,
        skill=payload.skill.strip() if payload.skill else None,
    )

    skill_names = [s.strip() for s in payload.skills if s.strip()]
    if user.skill and user.skill not in skill_names:
        skill_names.insert(0, user.skill)

    for skill_name in skill_names:
        skill = db.query(Skill).filter(Skill.name == skill_name).first()
        if not skill:
            skill = Skill(name=skill_name)
            db.add(skill)
        user.skills.append(skill)

    db.add(user)
    db.commit()
    db.refresh(user)
    return AuthResponse(user_id=user.id, username=user.username)


@app.post("/auth/login", response_model=AuthResponse)
def login_user(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username.strip()).first()
    if not user or user.password_hash != _hash_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return AuthResponse(user_id=user.id, username=user.username)


@app.get("/users/{user_id}", response_model=UserPublic)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserPublic(
        id=user.id,
        username=user.username,
        dob=user.dob.isoformat(),
        skill=user.skill,
        skills=[skill.name for skill in user.skills],
    )


@app.get("/users/{user_id}/favorites", response_model=FavoriteJobIdsResponse)
def get_favorites(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    favorites = db.query(Favorite).filter(Favorite.user_id == user_id).all()
    return FavoriteJobIdsResponse(user_id=user_id, job_ids=[fav.job_id for fav in favorites])


@app.post("/users/{user_id}/favorites/{job_id}", response_model=FavoriteJobIdsResponse)
def toggle_favorite(user_id: int, job_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    favorite = db.query(Favorite).filter(Favorite.user_id == user_id, Favorite.job_id == job_id).first()
    if favorite:
        db.delete(favorite)
    else:
        db.add(Favorite(user_id=user_id, job_id=job_id))
    db.commit()

    favorites = db.query(Favorite).filter(Favorite.user_id == user_id).all()
    return FavoriteJobIdsResponse(user_id=user_id, job_ids=[fav.job_id for fav in favorites])
