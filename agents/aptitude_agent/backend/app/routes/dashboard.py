from flask import Blueprint, g
from ..models import AptitudeTest
from ..services.analytics_service import analytics_payload
from ..services.job_service import abandon_stale_tests
from ..utils.authentication import require_student
from .common import test_summary

bp=Blueprint("dashboard",__name__,url_prefix="/api/aptitude")

@bp.get("/dashboard")
@require_student
def dashboard():
    abandon_stale_tests(g.student.id)
    completed=AptitudeTest.query.filter_by(student_id=g.student.id,status="completed").order_by(AptitudeTest.completed_at.desc()).all()
    average=round(sum(float(test.percentage) for test in completed)/len(completed),1) if completed else 0
    analytics=analytics_payload(list(reversed(completed)))
    return {"tests_completed":len(completed),"average_score":average,"best_score":max([float(test.percentage) for test in completed],default=0),"accuracy":average,"strongest_area":analytics["strongest_area"],"focus_area":analytics["focus_area"],"categories":analytics["categories"],"score_trend":analytics["score_trend"],"recent_tests":[test_summary(test) for test in completed[:4]]}
