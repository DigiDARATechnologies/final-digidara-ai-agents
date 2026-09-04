"""List and explicitly approve or retire validated bank items."""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app import create_app
from backend.app.extensions import db
from backend.app.models import QuestionBankItem
from backend.app.services.question_bank_service import bank_inventory


def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("inventory")
    list_parser=sub.add_parser("list");list_parser.add_argument("--status",choices=["draft","review","approved","retired"],default="review");list_parser.add_argument("--limit",type=int,default=20)
    for command in ("approve","retire"):
        action=sub.add_parser(command);action.add_argument("ids",nargs="+")
    args=parser.parse_args();app=create_app()
    with app.app_context():
        if args.command=="inventory":
            for row in bank_inventory():print(f"{row['category']} | {row['difficulty']} | {row['status']} | {row['count']}")
        elif args.command=="list":
            for item in QuestionBankItem.query.filter_by(status=args.status).order_by(QuestionBankItem.created_at).limit(args.limit):print(f"{item.id} | {item.category} | {item.topic} | {item.difficulty}\n  {item.question_text[:180]}")
        else:
            items=QuestionBankItem.query.filter(QuestionBankItem.id.in_(args.ids)).all()
            status="approved" if args.command=="approve" else "retired"
            for item in items:item.status=status;item.approved_at=datetime.now(timezone.utc) if status=="approved" else None
            db.session.commit();print(f"Updated {len(items)} items to {status}")


if __name__=="__main__":main()
