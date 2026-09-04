"""Add structural question fingerprints and backfill existing content.

Revision ID: 0013_structural_deduplication
Revises: 0012_production_foundation
"""
import hashlib
import re
from decimal import Decimal, InvalidOperation

from alembic import op
import sqlalchemy as sa


revision="0013_structural_deduplication"
down_revision="0012_production_foundation"
branch_labels=None
depends_on=None


NUMBER_PATTERN=re.compile(
    r"(?<!\w)(?P<number>-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*(?P<percent>%?)(?!\w)"
)


def fingerprint(text,category,topic):
    values=[]
    for match in NUMBER_PATTERN.finditer(text or ""):
        raw=match.group("number").replace(",","")
        try:number=format(Decimal(raw).normalize(),"f")
        except InvalidOperation:number=raw
        if number in {"-0","-0.0"}:number="0"
        kind="percent" if match.group("percent") else "number"
        values.append(f"{kind}:{number}")
    if len(values)<2:return None
    signature="|".join((category.casefold().strip(),topic.casefold().strip(),*sorted(values)))
    return hashlib.sha256(signature.encode()).hexdigest()


def upgrade():
    op.add_column("aptitude_test_questions",sa.Column("structural_hash",sa.String(64)))
    op.create_index("ix_aptitude_test_questions_structural_hash","aptitude_test_questions",["structural_hash"])
    op.add_column("aptitude_recent_question_hashes",sa.Column("structural_hash",sa.String(64)))
    op.create_index("ix_recent_hash_structural","aptitude_recent_question_hashes",["structural_hash"])
    op.add_column("aptitude_question_bank",sa.Column("structural_hash",sa.String(64)))
    op.create_index("ix_aptitude_question_bank_structural_hash","aptitude_question_bank",["structural_hash"])

    bind=op.get_bind()
    question_rows=bind.execute(sa.text("SELECT id,test_id,category,topic,question_text,content_hash FROM aptitude_test_questions")).mappings().all()
    by_test_content={}
    for row in question_rows:
        value=fingerprint(row["question_text"],row["category"],row["topic"])
        bind.execute(sa.text("UPDATE aptitude_test_questions SET structural_hash=:value WHERE id=:id"),{"value":value,"id":row["id"]})
        by_test_content[(row["test_id"],row["content_hash"])]=value

    recent_rows=bind.execute(sa.text("SELECT id,test_id,content_hash FROM aptitude_recent_question_hashes")).mappings().all()
    for row in recent_rows:
        value=by_test_content.get((row["test_id"],row["content_hash"]))
        bind.execute(sa.text("UPDATE aptitude_recent_question_hashes SET structural_hash=:value WHERE id=:id"),{"value":value,"id":row["id"]})

    bank_rows=bind.execute(sa.text("SELECT id,category,topic,question_text FROM aptitude_question_bank")).mappings().all()
    for row in bank_rows:
        value=fingerprint(row["question_text"],row["category"],row["topic"])
        bind.execute(sa.text("UPDATE aptitude_question_bank SET structural_hash=:value WHERE id=:id"),{"value":value,"id":row["id"]})

    bind.execute(sa.text("UPDATE aptitude_question_bank SET status='retired', approved_at=NULL WHERE LOWER(CONCAT(question_text,' ',option_a,' ',option_b,' ',option_c,' ',option_d,' ',explanation)) LIKE '%scenario\\_seed%' ESCAPE '\\\\'"))


def downgrade():
    op.drop_index("ix_aptitude_question_bank_structural_hash",table_name="aptitude_question_bank")
    op.drop_column("aptitude_question_bank","structural_hash")
    op.drop_index("ix_recent_hash_structural",table_name="aptitude_recent_question_hashes")
    op.drop_column("aptitude_recent_question_hashes","structural_hash")
    op.drop_index("ix_aptitude_test_questions_structural_hash",table_name="aptitude_test_questions")
    op.drop_column("aptitude_test_questions","structural_hash")
