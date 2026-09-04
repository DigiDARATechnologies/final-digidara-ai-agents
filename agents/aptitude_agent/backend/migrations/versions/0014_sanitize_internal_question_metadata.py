"""Sanitize internal generation metadata from historical content.

Revision ID: 0014_sanitize_internal_metadata
Revises: 0013_structural_deduplication
"""
import hashlib
import re
from decimal import Decimal, InvalidOperation

from alembic import op
import sqlalchemy as sa


revision="0014_sanitize_internal_metadata"
down_revision="0013_structural_deduplication"
branch_labels=None
depends_on=None


TOKEN=r"(?:scenario[_\s-]?seed|variation[_\s-]?seed)"
WITH_TOKEN=re.compile(rf"\bwith\s+{TOKEN}\s*(?:is|=|:)?\s*['\"]?[a-z0-9-]{{4,}}['\"]?",re.IGNORECASE)
TOKEN_VALUE=re.compile(rf"\b{TOKEN}\s*(?:is|=|:)?\s*['\"]?[a-z0-9-]{{4,}}['\"]?",re.IGNORECASE)
NUMBER_PATTERN=re.compile(r"(?<!\w)(?P<number>-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*(?P<percent>%?)(?!\w)")


def clean(value):
    value=WITH_TOKEN.sub("with a varied scenario",value or "")
    return TOKEN_VALUE.sub("scenario",value)


def exact_hash(text):
    return hashlib.sha256(re.sub(r"\W+","",text.lower()).encode()).hexdigest()


def fingerprint(text,category,topic):
    values=[]
    for match in NUMBER_PATTERN.finditer(text or ""):
        raw=match.group("number").replace(",","")
        try:number=format(Decimal(raw).normalize(),"f")
        except InvalidOperation:number=raw
        if number in {"-0","-0.0"}:number="0"
        values.append(f"{'percent' if match.group('percent') else 'number'}:{number}")
    if len(values)<2:return None
    signature="|".join((category.casefold().strip(),topic.casefold().strip(),*sorted(values)))
    return hashlib.sha256(signature.encode()).hexdigest()


def upgrade():
    bind=op.get_bind()
    rows=bind.execute(sa.text(
        "SELECT id,test_id,category,topic,question_text,option_a,option_b,option_c,option_d,explanation,content_hash "
        "FROM aptitude_test_questions"
    )).mappings().all()
    for row in rows:
        fields={name:clean(row[name]) for name in ("question_text","option_a","option_b","option_c","option_d","explanation")}
        if all(fields[name]==row[name] for name in fields):continue
        new_content_hash=exact_hash(fields["question_text"])
        new_structural_hash=fingerprint(fields["question_text"],row["category"],row["topic"])
        bind.execute(sa.text(
            "UPDATE aptitude_test_questions SET question_text=:question_text,option_a=:option_a,option_b=:option_b,"
            "option_c=:option_c,option_d=:option_d,explanation=:explanation,content_hash=:content_hash,"
            "structural_hash=:structural_hash WHERE id=:id"
        ),{**fields,"content_hash":new_content_hash,"structural_hash":new_structural_hash,"id":row["id"]})
        bind.execute(sa.text(
            "UPDATE aptitude_recent_question_hashes SET content_hash=:new_content_hash,structural_hash=:structural_hash "
            "WHERE test_id=:test_id AND content_hash=:old_content_hash"
        ),{"new_content_hash":new_content_hash,"structural_hash":new_structural_hash,"test_id":row["test_id"],"old_content_hash":row["content_hash"]})

    bank_rows=bind.execute(sa.text(
        "SELECT id,category,topic,question_text,option_a,option_b,option_c,option_d,explanation FROM aptitude_question_bank"
    )).mappings().all()
    for row in bank_rows:
        fields={name:clean(row[name]) for name in ("question_text","option_a","option_b","option_c","option_d","explanation")}
        if all(fields[name]==row[name] for name in fields):continue
        bind.execute(sa.text(
            "UPDATE aptitude_question_bank SET question_text=:question_text,option_a=:option_a,option_b=:option_b,"
            "option_c=:option_c,option_d=:option_d,explanation=:explanation,content_hash=:content_hash,"
            "structural_hash=:structural_hash,status='retired',approved_at=NULL WHERE id=:id"
        ),{**fields,"content_hash":exact_hash(fields["question_text"]),"structural_hash":fingerprint(fields["question_text"],row["category"],row["topic"]),"id":row["id"]})


def downgrade():
    # Sanitized internal metadata is intentionally not restored.
    pass
