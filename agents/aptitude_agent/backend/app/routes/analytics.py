from flask import Blueprint, g
from ..models import AptitudeTest
from ..services.analytics_service import analytics_payload
from ..utils.authentication import require_student

bp=Blueprint("analytics",__name__,url_prefix="/api/aptitude")

@bp.get("/analytics")
@require_student
def analytics():
    tests=AptitudeTest.query.filter_by(student_id=g.student.id,status="completed").order_by(AptitudeTest.completed_at).all()
    return analytics_payload(tests)

