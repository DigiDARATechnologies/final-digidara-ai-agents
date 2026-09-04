from flask import has_request_context, request
from ..extensions import db
from ..models import AuditEvent


def record_event(event_type, student_id=None, test_id=None, metadata=None, commit=False):
    request_id = request.environ.get("aptitude.request_id") if has_request_context() else None
    event = AuditEvent(event_type=event_type, student_id=student_id, test_id=test_id, request_id=request_id, metadata_json=metadata or {})
    db.session.add(event)
    if commit: db.session.commit()
    return event
