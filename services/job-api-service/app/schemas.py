from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JobListItem(BaseModel):
    id: str
    intitule: str | None
    description: str | None
    date_actualisation: datetime | None

    model_config = ConfigDict(from_attributes=True)


class JobDetail(BaseModel):
    id: str
    intitule: str | None
    description: str | None
    date_creation: datetime | None
    date_actualisation: datetime | None
    lieu_travail: str | None
    entreprise_nom: str | None
    commune: str | None
    # raw_data: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    username: str
    password: str = Field(min_length=4)
    dob: str
    skill: str | None = None
    skills: list[str] = []


class LoginRequest(BaseModel):
    username: str
    password: str


class UserPublic(BaseModel):
    id: int
    username: str
    dob: str
    skill: str | None
    skills: list[str]


class AuthResponse(BaseModel):
    user_id: int
    username: str


class FavoriteJobIdsResponse(BaseModel):
    user_id: int
    job_ids: list[str]
