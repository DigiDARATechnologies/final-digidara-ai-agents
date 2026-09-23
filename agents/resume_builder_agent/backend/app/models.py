from datetime import date, datetime, timezone

from sqlalchemy import Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.sql import func

from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())

    resumes = db.relationship(
        "Resume",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Resume(db.Model):
    __tablename__ = "resumes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.String(64),
        db.ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(255), nullable=False)
    target_role = db.Column(db.String(255))
    experience_level = db.Column(db.String(20))
    template_choice = db.Column(db.String(100), nullable=False, default="default")
    status = db.Column(db.String(30), nullable=False, default="draft")
    summary = db.Column(Text)
    profile_photo = db.Column(db.String(500), nullable=True)
    declaration = db.Column(Text)
    declaration_enabled = db.Column(db.Boolean, nullable=False, default=True)
    ats_score = db.Column(db.Integer)
    job_match_score = db.Column(db.Integer)
    download_count = db.Column(db.Integer, nullable=False, default=0)
    last_downloaded_at = db.Column(db.DateTime)
    last_analyzed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=utc_now,
    )

    user = db.relationship("User", back_populates="resumes")
    personal_info = db.relationship(
        "PersonalInfo",
        back_populates="resume",
        cascade="all, delete-orphan",
        uselist=False,
    )
    education = db.relationship(
        "Education",
        back_populates="resume",
        cascade="all, delete-orphan",
    )
    experience = db.relationship(
        "Experience",
        back_populates="resume",
        cascade="all, delete-orphan",
    )
    skills = db.relationship(
        "Skill",
        back_populates="resume",
        cascade="all, delete-orphan",
    )
    certifications = db.relationship(
        "Certification",
        back_populates="resume",
        cascade="all, delete-orphan",
    )
    projects = db.relationship(
        "Project",
        back_populates="resume",
        cascade="all, delete-orphan",
    )
    publications = db.relationship(
        "Publication",
        back_populates="resume",
        cascade="all, delete-orphan",
    )
    achievements = db.relationship(
        "Achievement",
        back_populates="resume",
        cascade="all, delete-orphan",
    )
    languages = db.relationship(
        "Language",
        back_populates="resume",
        cascade="all, delete-orphan",
    )
    ats_analyses = db.relationship(
        "AtsAnalysis",
        back_populates="resume",
        cascade="all, delete-orphan",
    )


class AtsAnalysis(db.Model):
    __tablename__ = "ats_analyses"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(
        db.Integer,
        db.ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.String(64), nullable=False, index=True)
    analysis_type = db.Column(db.String(40), nullable=False)
    final_score = db.Column(db.Integer, nullable=False)
    scoring_version = db.Column(db.String(40), nullable=False)
    job_description = db.Column(Text)
    breakdown = db.Column(JSON)
    matched_requirements = db.Column(JSON)
    missing_requirements = db.Column(JSON)
    recommendations = db.Column(JSON)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())

    resume = db.relationship("Resume", back_populates="ats_analyses")


class PersonalInfo(db.Model):
    __tablename__ = "personal_info"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(
        db.Integer,
        db.ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50))
    location = db.Column(db.String(255))
    links = db.Column(JSON)

    resume = db.relationship("Resume", back_populates="personal_info")


class Education(db.Model):
    __tablename__ = "education"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(
        db.Integer,
        db.ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    school = db.Column(db.String(255), nullable=False, default="")
    degree = db.Column(db.String(255), default="")
    level = db.Column(db.String(30), default="")
    field = db.Column(db.String(255), default="")
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    cgpa = db.Column(db.String(20))
    percentage = db.Column(db.String(20))

    resume = db.relationship("Resume", back_populates="education")


class Experience(db.Model):
    __tablename__ = "experience"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(
        db.Integer,
        db.ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(255), nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    is_current = db.Column(db.Boolean, nullable=False, default=False)
    raw_input = db.Column(Text)
    ai_generated_bullets = db.Column(JSON)

    resume = db.relationship("Resume", back_populates="experience")


class Skill(db.Model):
    __tablename__ = "skills"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(
        db.Integer,
        db.ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_name = db.Column(db.String(150), nullable=False)

    resume = db.relationship("Resume", back_populates="skills")


class Certification(db.Model):
    __tablename__ = "certifications"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(
        db.Integer,
        db.ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(255), nullable=False)
    issuer = db.Column(db.String(255))
    date = db.Column(db.Date)

    resume = db.relationship("Resume", back_populates="certifications")


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(
        db.Integer,
        db.ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(Text)
    ai_generated_bullets = db.Column(JSON)

    resume = db.relationship("Resume", back_populates="projects")


class Publication(db.Model):
    __tablename__ = "publications"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(
        db.Integer,
        db.ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(Text)
    date = db.Column(db.Date)

    resume = db.relationship("Resume", back_populates="publications")


class Language(db.Model):
    __tablename__ = "languages"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(
        db.Integer,
        db.ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    language_name = db.Column(db.String(100), nullable=False)
    proficiency = db.Column(db.String(50))

    resume = db.relationship("Resume", back_populates="languages")


class Achievement(db.Model):
    __tablename__ = "achievements"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(
        db.Integer,
        db.ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(Text)
    date = db.Column(db.Date)

    resume = db.relationship("Resume", back_populates="achievements")
