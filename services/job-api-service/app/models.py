from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, Table, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Text, primary_key=True, index=True)
    intitule = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    date_creation = Column(DateTime, nullable=True)
    date_actualisation = Column(DateTime, nullable=True)
    lieu_travail = Column(Text, nullable=True)
    rome_code = Column(Text, nullable=True)
    entreprise_nom = Column(Text, nullable=True)
    type_contrat = Column(Text, nullable=True)
    type_contrat_libelle = Column(Text, nullable=True)
    nature_contrat = Column(Text, nullable=True)
    experience_exige = Column(Text, nullable=True)
    experience_libelle = Column(Text, nullable=True)
    salaire = Column(Text, nullable=True)
    alternance = Column(Boolean, nullable=True)
    qualification_code = Column(Text, nullable=True)
    qualification_libelle = Column(Text, nullable=True)
    code_naf = Column(Text, nullable=True)
    secteur_activite = Column(Text, nullable=True)
    secteur_activite_libelle = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    commune = Column(Text, nullable=True)
    raw_data = Column(JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now())


user_skills = Table(
    "user_skills",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("skill_id", Integer, ForeignKey("skills.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(Text, unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    dob = Column(Date, nullable=False)
    skill = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    skills = relationship("Skill", secondary=user_skills, back_populates="users")
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, unique=True, nullable=False, index=True)

    users = relationship("User", secondary=user_skills, back_populates="skills")


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    job_id = Column(Text, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", back_populates="favorites")

    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_user_job_favorite"),)
