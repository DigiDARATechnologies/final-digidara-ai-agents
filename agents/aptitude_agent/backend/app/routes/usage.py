from flask import Blueprint, g
from ..services.usage_service import usage_payload
from ..utils.authentication import require_student

bp=Blueprint("usage",__name__,url_prefix="/api/aptitude")

@bp.get("/usage")
@require_student
def usage():
    return usage_payload(g.student.id)
