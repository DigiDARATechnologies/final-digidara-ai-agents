"""Generate validated question-bank candidates outside the live test path."""
import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app import create_app
from backend.app.extensions import db
from backend.app.models import QuestionBankItem
from backend.app.services.test_generation import CATEGORIES, generate_questions
from backend.app.services.question_validation import numeric_pattern


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--copies",type=int,default=1,help="Questions per topic/difficulty combination")
    parser.add_argument("--category",choices=list(CATEGORIES))
    parser.add_argument("--approve",action="store_true",help="Approve immediately; omit for human review")
    args=parser.parse_args()
    if args.copies<1 or args.copies>20:raise SystemExit("--copies must be between 1 and 20")
    app=create_app()
    with app.app_context():
        slots=[]
        categories={args.category:CATEGORIES[args.category]} if args.category else CATEGORIES
        for category,topics in categories.items():
            for topic in topics:
                for difficulty in ("Easy","Medium","Hard"):
                    slots.extend({"category":category,"topic":topic,"difficulty":difficulty} for _ in range(args.copies))
        created=duplicates=0
        for offset in range(0,len(slots),10):
            recent_bank=QuestionBankItem.query.order_by(QuestionBankItem.created_at.desc()).limit(200).all()
            avoid_patterns=[numeric_pattern(row.question_text) for row in recent_bank if numeric_pattern(row.question_text)]
            questions,model,_usage=generate_questions(slots[offset:offset+10],avoid_questions=[row.question_text for row in recent_bank],avoid_number_patterns=avoid_patterns)
            for item in questions:
                duplicate=QuestionBankItem.query.filter_by(content_hash=item["content_hash"]).first()
                if not duplicate and item["structural_hash"]:duplicate=QuestionBankItem.query.filter_by(structural_hash=item["structural_hash"]).first()
                if duplicate:duplicates+=1;continue
                approved_at=datetime.now(timezone.utc) if args.approve else None
                db.session.add(QuestionBankItem(id=str(uuid.uuid4()),category=item["category"],topic=item["topic"],difficulty=item["difficulty"],question_text=item["question"],option_a=item["options"]["A"],option_b=item["options"]["B"],option_c=item["options"]["C"],option_d=item["options"]["D"],correct_answer=item["correct_answer"],explanation=item["explanation"],content_hash=item["content_hash"],structural_hash=item["structural_hash"],status="approved" if args.approve else "review",approved_at=approved_at,source_model=model,prompt_version="bank-v1",option_counts_json={"A":0,"B":0,"C":0,"D":0,"timeout":0}))
                created+=1
            db.session.commit()
        print(f"Created {created} bank items; skipped {duplicates} duplicates; status={'approved' if args.approve else 'review'}")


if __name__=="__main__":main()
