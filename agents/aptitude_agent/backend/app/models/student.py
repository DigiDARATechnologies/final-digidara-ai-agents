from ..extensions import db
from .base import utcnow


class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.String(128), primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    email = db.Column(db.String(255))
    password_hash = db.Column(db.String(255))
    token_version = db.Column(db.Integer, default=0, nullable=False)
    phone = db.Column(db.String(24))
    course = db.Column(db.String(160))
    department = db.Column(db.String(160))
    year = db.Column(db.String(40))
    institution = db.Column(db.String(200))
    batch = db.Column(db.String(80))
    profile_photo = db.Column(db.LargeBinary(length=3 * 1024 * 1024))
    profile_photo_mime = db.Column(db.String(40))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    # DPDP (Digital Personal Data Protection Act) consent record -- when the
    # learner last agreed to a specific version of the data-processing
    # notice. See routes/privacy.py.
    data_consent_at = db.Column(db.DateTime(timezone=True))
    data_consent_version = db.Column(db.String(20))
    __table_args__ = (db.UniqueConstraint("email", name="uq_students_email"),)
