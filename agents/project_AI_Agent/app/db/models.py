import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return uuid.uuid4().hex


class CourseMedium(str, enum.Enum):
    local = "local"
    api = "api"


class EnrollmentStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"


class AssignmentStatus(str, enum.Enum):
    awaiting_topic_choice = "awaiting_topic_choice"
    awaiting_timer_confirm = "awaiting_timer_confirm"
    in_progress = "in_progress"
    awaiting_submission = "awaiting_submission"
    submitted = "submitted"
    needs_revision = "needs_revision"
    graded = "graded"


class SubmissionStatus(str, enum.Enum):
    processing = "processing"
    needs_revision = "needs_revision"
    graded = "graded"
    error = "error"
    # Content grade passed; waiting on the post-grading viva (oral defense)
    # before the score is revealed. See app/viva.py.
    pending_viva = "pending_viva"


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Required for the certificate-gated flow (eligibility_check/eligible_courses
    # key student lookup on it, matching real enrollment records). Nullable
    # because the free-topic flow (eligibility_check_free) has no enrollment
    # records to match against and keys students on their verified email
    # instead — a logged-in account with no phone on file (e.g. Google
    # sign-in) shouldn't be unable to use it.
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    medium: Mapped[CourseMedium] = mapped_column(Enum(CourseMedium), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Enrollment(Base):
    __tablename__ = "enrollments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    student_id: Mapped[str] = mapped_column(String(32), ForeignKey("students.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    status: Mapped[EnrollmentStatus] = mapped_column(
        Enum(EnrollmentStatus), nullable=False, default=EnrollmentStatus.in_progress
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    student_id: Mapped[str] = mapped_column(String(32), ForeignKey("students.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    certificate_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ProjectAssignment(Base):
    __tablename__ = "project_assignments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    thread_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, default=_uuid)
    student_id: Mapped[str] = mapped_column(String(32), ForeignKey("students.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    topic_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    medium: Mapped[CourseMedium] = mapped_column(Enum(CourseMedium), nullable=False)
    chosen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus), nullable=False, default=AssignmentStatus.awaiting_topic_choice
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    submissions: Mapped[list["Submission"]] = relationship(back_populates="assignment")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    assignment_id: Mapped[str] = mapped_column(String(32), ForeignKey("project_assignments.id"), nullable=False)
    docx_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    zip_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    docx_validation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    zip_validation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    score_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus), nullable=False, default=SubmissionStatus.processing
    )
    # Post-grading viva (oral defense). Populated once the content grade
    # passes; see app/viva.py and POST /api/viva/answer.
    viva_questions_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    viva_answers_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    viva_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    viva_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    assignment: Mapped[ProjectAssignment] = relationship(back_populates="submissions")


class LlmUsage(Base):
    """One row per LLM call — platform-wide token usage visibility, not
    per-user attribution (there's no per-user LLM quota concept yet)."""

    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(50))
    model_name: Mapped[str] = mapped_column(String(100))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    request_type: Mapped[str] = mapped_column(String(64), default="unspecified")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
