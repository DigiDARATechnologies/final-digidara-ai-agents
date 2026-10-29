"""Coins SkillDARA gives an organization's people.

The platform admin sets, per organization, how many coins each admin
(owner or admin), each staff login and each student gets. A person gets them
once per organization and role, when they get access: the owner when the
organization is created, staff when their login is made, a student when they
join (by code, from the student list, on approval or added by an admin).
Someone moved up to staff later also gets the staff coins.

Each grant is a paid, zero-rupee payment row (plan "org_coins", order id
manual_org_...), so it shows in the admin's payments as a manual grant and
in the learner's billing history. Its unique order id is also what makes a
grant happen only once, even when a student leaves and joins again.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app import db
from app.auth.service import add_credit
from app.billing.plans import FREE_TOKENS_PER_POINT
from app.models import Organization, OrganizationMember, Payment, User

logger = logging.getLogger(__name__)

PLAN_ID = "org_coins"
MAX_COINS = 1_000_000
# Organization role -> (Organization column, the role group a grant is for).
ROLE_FIELDS = {"owner": "admin_coins", "admin": "admin_coins", "staff": "staff_coins", "member": "student_coins"}


def clean(value) -> int:
    """A coin amount as entered: a whole number from 0 to MAX_COINS."""
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, min(MAX_COINS, number))


def _order_id(org_id: str, user_id: str, field: str) -> str:
    digest = hashlib.sha1(f"{org_id}:{user_id}:{field}".encode()).hexdigest()
    return f"manual_org_{digest}"


def grant(org_id: str, user_id: str, role: str) -> int:
    """Gives this person the organization's coins for their role, unless they
    already got them. Returns the coins given (0: none). Never raises: a
    failed grant must not stop someone joining."""
    field = ROLE_FIELDS.get(role)
    if field is None:
        return 0
    session = db.get_session()
    try:
        org = session.get(Organization, org_id)
        coins = clean(getattr(org, field, 0)) if org is not None else 0
        if not coins:
            return 0
        order_id = _order_id(org_id, user_id, field)
        if session.query(Payment.id).filter_by(razorpay_order_id=order_id).first() is not None:
            return 0
        user = session.get(User, user_id, with_for_update=True)
        if user is None:
            return 0
        tokens = int(coins * FREE_TOKENS_PER_POINT)
        session.add(Payment(user_id=user_id, plan_id=PLAN_ID, amount=0, currency="INR", razorpay_order_id=order_id,
                            razorpay_payment_id=None, status="paid", paid_at=datetime.utcnow(),
                            credited_tokens=tokens, credited_points=float(coins)))
        add_credit(user, tokens, coins)
        session.commit()
        return coins
    except IntegrityError:
        session.rollback()          # granted at the same moment by another request
        return 0
    except Exception:
        session.rollback()
        logger.warning("organization coins not granted org=%s user=%s", org_id, user_id, exc_info=True)
        return 0
    finally:
        session.close()


def grant_current_members(org_id: str) -> dict:
    """Platform admin: gives the coins to everyone already in the
    organization who has not had them for their role yet."""
    session = db.get_session()
    try:
        members = [(m.user_id, m.role) for m in session.query(OrganizationMember).filter_by(organization_id=org_id).all()]
    finally:
        session.close()
    given = {"people": 0, "coins": 0}
    for user_id, role in members:
        coins = grant(org_id, user_id, role)
        if coins:
            given["people"] += 1
            given["coins"] += coins
    return given
