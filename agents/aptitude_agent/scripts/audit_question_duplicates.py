"""Audit stored questions for leaked prompt metadata and repeated structures."""
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from backend.app import create_app
from backend.app.extensions import db


def main():
    app=create_app()
    with app.app_context():
        combined="LOWER(CONCAT(question_text,option_a,option_b,option_c,option_d,explanation))"
        leaked=db.session.execute(
            text(f"SELECT id,test_id,sequence_no,question_text FROM aptitude_test_questions WHERE {combined} LIKE :scenario OR {combined} LIKE :variation"),
            {"scenario":"%scenario_seed%","variation":"%variation_seed%"},
        ).mappings().all()
        duplicates=db.session.execute(text(
            "SELECT student_id,structural_hash,COUNT(*) AS count "
            "FROM aptitude_recent_question_hashes WHERE structural_hash IS NOT NULL "
            "GROUP BY student_id,structural_hash HAVING COUNT(*)>1"
        )).mappings().all()
        coverage=db.session.execute(text(
            "SELECT COUNT(*) total,SUM(structural_hash IS NOT NULL) fingerprinted "
            "FROM aptitude_test_questions"
        )).mappings().one()
        print(f"Questions: {coverage['total']} total; {coverage['fingerprinted'] or 0} numeric structures fingerprinted")
        print(f"Internal-token leaks: {len(leaked)}")
        for row in leaked:print(f"  {row['test_id']} question {row['sequence_no']}: {row['question_text'][:180]}")
        print(f"Repeated recent structures: {len(duplicates)}")
        for row in duplicates:print(f"  learner={row['student_id']} count={row['count']} hash={row['structural_hash']}")


if __name__=="__main__":main()
