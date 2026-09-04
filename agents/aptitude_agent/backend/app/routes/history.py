from flask import Blueprint, g
from ..models import AptitudeTest
from ..utils.authentication import require_student
from .common import test_summary

bp=Blueprint("history",__name__,url_prefix="/api/aptitude")

@bp.get("/history")
@require_student
def history():
    tests=AptitudeTest.query.filter_by(student_id=g.student.id,status="completed").order_by(AptitudeTest.completed_at.desc()).all()
    return {"tests":[test_summary(test) for test in tests]}
