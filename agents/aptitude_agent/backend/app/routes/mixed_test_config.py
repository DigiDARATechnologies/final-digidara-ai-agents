from flask import Blueprint, g, request

from ..extensions import db
from ..services.audit_service import record_event
from ..services.mixed_test_config_service import (
    ensure_mixed_test_config, serialize_mixed_test_config,
    update_mixed_test_config, validate_mixed_test_update,
)
from ..utils.authentication import require_student
from ..utils.errors import APIError


bp = Blueprint("mixed_test_config", __name__, url_prefix="/api/learner")


@bp.get("/mixed-test-config")
@require_student
def get_mixed_test_config():
    rows = ensure_mixed_test_config(g.student.id)
    db.session.commit()
    return serialize_mixed_test_config(rows)


@bp.put("/mixed-test-config")
@require_student
def put_mixed_test_config():
    try:
        counts = validate_mixed_test_update(request.get_json(silent=True))
    except ValueError as exc:
        raise APIError(str(exc), 400, "invalid_mixed_test_config") from exc
    rows = update_mixed_test_config(g.student.id, counts)
    record_event(
        "mixed_test_config_updated", g.student.id,
        metadata={"counts": counts, "total_questions": sum(counts.values())},
    )
    db.session.commit()
    return serialize_mixed_test_config(rows)
