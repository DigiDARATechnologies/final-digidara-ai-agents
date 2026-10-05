import hashlib
import hmac
import logging
import os
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import func, update

from app.auth import service as auth_service
from app.auth.security import decode_access_token, get_current_user_id
from app.billing import invoice as invoice_pdf
from app.billing.plans import (
    PLANS,
    active_plan,
    credited_points,
    exact_credit,
    is_admin_test_price,
    is_full_price,
    offered_plans,
    payment_label,
    plan_name,
    points_for_payment,
    points_for_tokens,
)
from app.db import get_session
from app.models import Payment, TokenUsageEvent
from app.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])

# Per account. Each order is a call to Razorpay with our key, and verify
# re-checks a payment with Razorpay; neither needs more than a few a minute.
_ORDER_RATE_LIMIT = "10/minute"
_VERIFY_RATE_LIMIT = "30/minute"


class OrderRequest(BaseModel):
    plan_id: str


class VerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


def _credentials() -> tuple[str, str]:
    key_id = os.environ.get("RAZORPAY_KEY_ID", "").strip()
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "").strip()
    if not key_id or not key_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Razorpay is not configured.")
    return key_id, key_secret


def _mark_paid(session, payment: Payment, razorpay_payment_id: str | None) -> bool:
    """Flip a payment to paid exactly once; True only for the caller that did it.

    A conditional UPDATE, not read-then-write: verify and the Razorpay webhook
    can arrive together for the same payment, and both used to see "created"
    and both credit tokens. Only the request whose UPDATE changes a row may
    credit. The same UPDATE records what the payment credits, so the record
    and the flip can never disagree.
    """
    credit = _exact_credit(payment)
    result = session.execute(
        update(Payment)
        .where(Payment.id == payment.id, Payment.status != "paid")
        .values(
            status="paid", razorpay_payment_id=razorpay_payment_id, paid_at=datetime.utcnow(),
            credited_tokens=credit[0] if credit else 0,
            credited_points=credit[1] if credit else 0,
        )
    )
    session.commit()
    return result.rowcount == 1


def _credit_for_payment(payment: Payment) -> None:
    # Exactly the plan's tokens and points, from the server's own catalog and
    # the amount Razorpay confirmed -- never from anything the browser sent,
    # never scaled. A payment that matches no plan price credits nothing.
    credit = _exact_credit(payment)
    if credit is None:
        logger.warning(
            "payment %s (plan %s, %s %s paise) matches no plan price; nothing credited -- review and credit by hand",
            payment.id, payment.plan_id, payment.currency, payment.amount,
        )
        return
    tokens, points = credit
    auth_service.credit_tokens(payment.user_id, tokens, points)


def _is_admin(user_id: str | None) -> bool:
    user = auth_service.get_by_id(user_id) if user_id else None
    return bool(user and user.is_admin)


def _exact_credit(payment: Payment) -> tuple[int, int] | None:
    return exact_credit(payment.plan_id, payment.amount, payment.currency, admin=_is_admin(payment.user_id))


@router.get("/plans")
def plans(request: Request) -> dict:
    """The plans on sale, so prices live in one place (app/billing/plans.py).
    Open to everyone; a signed-in admin also gets the test pages."""
    user_id = None
    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Bearer "):
        try:
            user_id = decode_access_token(authorization[7:])
        except HTTPException:
            user_id = None
    return {"plans": offered_plans(admin=_is_admin(user_id))}


@router.get("/summary")
def summary(user_id: str = Depends(get_current_user_id)) -> dict:
    session = get_session()
    try:
        payments = session.query(Payment).filter_by(user_id=user_id).order_by(Payment.created_at.desc()).limit(25).all()
        paid = sorted((p for p in payments if p.status == "paid"), key=lambda p: p.paid_at or p.created_at, reverse=True)
        plan_id, expires = active_plan(paid)
        return {
            "plan": plan_id,
            "plan_name": plan_name(plan_id),
            "plan_expires_at": expires.isoformat() if expires else None,
            "payments": [
                {
                    "id": p.id, "plan_id": p.plan_id, "label": payment_label(p.plan_id), "amount": p.amount,
                    "currency": p.currency, "status": p.status, "payment_id": p.razorpay_payment_id,
                    "points": credited_points(p) if p.status == "paid" else points_for_payment(p.plan_id, p.amount),
                    "created_at": p.created_at.isoformat(), "invoice_available": p.status == "paid",
                }
                for p in payments
            ],
        }
    finally:
        session.close()


@router.get("/token-balance")
def token_balance(user_id: str = Depends(get_current_user_id)) -> dict:
    user = auth_service.get_by_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account no longer exists.")
    # Users see points; tokens stay the unit everything is charged in.
    return {
        "balance": user.token_balance,
        "points": points_for_tokens(max(0, user.token_balance), user.tokens_per_point),
        "tokens_per_point": user.tokens_per_point,
    }


def month_start_utc(now_utc: datetime, offset_minutes: int) -> datetime:
    """The first moment of the user's current calendar month, as naive UTC.

    ``offset_minutes`` is the user's local time minus UTC (IST is +330), so the
    month turns over at the user's midnight, not the server's."""
    local = now_utc + timedelta(minutes=offset_minutes)
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(minutes=offset_minutes)


@router.get("/usage-month")
def usage_this_month(
    offset_minutes: int = Query(0, ge=-14 * 60, le=14 * 60),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """This calendar month's billed usage, overall and per agent.

    There is no fixed monthly quota: tokens are a balance. The limit is what
    the user had to spend this month -- what they used plus what is left --
    so it follows plans, top-ups and spending instead of a hardcoded number."""
    user = auth_service.get_by_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account no longer exists.")
    since = month_start_utc(datetime.utcnow(), offset_minutes)
    session = get_session()
    try:
        rows = (
            session.query(TokenUsageEvent.agent_name, func.coalesce(func.sum(TokenUsageEvent.tokens), 0), func.count(TokenUsageEvent.id))
            .filter(TokenUsageEvent.user_id == user_id, TokenUsageEvent.created_at >= since)
            .group_by(TokenUsageEvent.agent_name)
            .all()
        )
    finally:
        session.close()
    rate = user.tokens_per_point
    agents = [
        {"agent_name": name, "tokens": int(tokens), "points": points_for_tokens(int(tokens), rate), "requests": int(count)}
        for name, tokens, count in rows
    ]
    used = sum(agent["tokens"] for agent in agents)
    balance = max(0, int(user.token_balance))
    # Points use the account's current rate. A month that spans a purchase at
    # a different plan's rate is shown approximately; tokens stay exact.
    return {
        "month_start": since.isoformat() + "Z",
        "tokens_used": used,
        "requests": sum(agent["requests"] for agent in agents),
        "balance": balance,
        "limit": used + balance,
        "points_used": points_for_tokens(used, rate),
        "points_balance": points_for_tokens(balance, rate),
        "points_limit": points_for_tokens(used + balance, rate),
        "tokens_per_point": rate,
        "agents": agents,
    }


@router.post("/orders", status_code=201)
@limiter.limit(_ORDER_RATE_LIMIT)
def create_order(req: OrderRequest, request: Request, user_id: str = Depends(get_current_user_id)) -> dict:
    plan = PLANS.get(req.plan_id)
    if not plan:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown billing plan.")
    if plan.get("payment_page_url"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This plan is paid on its Razorpay payment page.")
    key_id, key_secret = _credentials()
    receipt = f"dd_{user_id[:10]}_{int(datetime.utcnow().timestamp())}"
    try:
        response = httpx.post("https://api.razorpay.com/v1/orders", auth=(key_id, key_secret), json={"amount": plan["amount"], "currency": plan["currency"], "receipt": receipt, "notes": {"user_id": user_id, "plan_id": req.plan_id}}, timeout=15)
        response.raise_for_status()
        order = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Unable to create payment order.") from exc
    session = get_session()
    try:
        payment = Payment(user_id=user_id, plan_id=req.plan_id, amount=plan["amount"], currency=plan["currency"], razorpay_order_id=order["id"])
        session.add(payment)
        session.commit()
    finally:
        session.close()
    return {"key_id": key_id, "order_id": order["id"], "amount": plan["amount"], "currency": plan["currency"], "name": f"{plan['name']} plan"}


@router.post("/verify")
@limiter.limit(_VERIFY_RATE_LIMIT)
def verify_payment(req: VerifyRequest, request: Request, user_id: str = Depends(get_current_user_id)) -> dict:
    key_id, key_secret = _credentials()
    session = get_session()
    try:
        payment = session.query(Payment).filter_by(user_id=user_id, razorpay_order_id=req.razorpay_order_id).first()
        if not payment:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment order not found.")
        expected = hmac.new(key_secret.encode(), f"{payment.razorpay_order_id}|{req.razorpay_payment_id}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, req.razorpay_signature):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid payment signature.")
        try:
            response = httpx.get(f"https://api.razorpay.com/v1/payments/{req.razorpay_payment_id}", auth=(key_id, key_secret), timeout=15)
            response.raise_for_status()
            remote = response.json()
        except httpx.HTTPError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Unable to confirm payment status.") from exc
        if remote.get("order_id") != payment.razorpay_order_id or remote.get("amount") != payment.amount or remote.get("currency") != payment.currency or remote.get("status") != "captured":
            raise HTTPException(status.HTTP_409_CONFLICT, "Payment has not been captured yet.")
        # Only the request that actually flips the row credits tokens, so a
        # client retry or a concurrent webhook can never credit twice.
        if _mark_paid(session, payment, req.razorpay_payment_id):
            _credit_for_payment(payment)
        return {"verified": True, "plan": payment.plan_id}
    finally:
        session.close()


@router.get("/invoices/{payment_id}")
def download_invoice(payment_id: str, user_id: str = Depends(get_current_user_id)) -> Response:
    session = get_session()
    try:
        payment = session.query(Payment).filter_by(id=payment_id, user_id=user_id).first()
        if not payment:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found.")
        if payment.status != "paid" or payment.paid_at is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "An invoice is available once the payment is complete.")
        user = auth_service.get_by_id(user_id)
        customer = {"name": getattr(user, "name", ""), "email": getattr(user, "email", ""), "mobile": getattr(user, "mobile", "") or ""}
        pdf = invoice_pdf.build_invoice_pdf(payment=payment, description=payment_label(payment.plan_id), customer=customer)
        filename = f"{invoice_pdf.invoice_number(payment.id, payment.paid_at)}.pdf"
        return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "private, no-store"})
    finally:
        session.close()


def _webhook_secrets() -> list[str]:
    """The in-app checkout's webhook and the payment page's (a different
    Razorpay account or mode can sign with its own secret)."""
    names = ("RAZORPAY_WEBHOOK_SECRET", "RAZORPAY_PAGE_WEBHOOK_SECRET")
    return [value for value in (os.environ.get(name, "").strip() for name in names) if value]


def _page_plan_for(amount: int, currency: str, admin: bool) -> str | None:
    for plan_id, plan in PLANS.items():
        if plan["currency"] != currency:
            continue
        if plan.get("payment_page_url") and is_full_price(plan, amount):
            return plan_id
        if admin and is_admin_test_price(plan, amount):
            return plan_id
    return None


def _credit_payment_page(session, entity: dict) -> None:
    """A captured payment the app did not create: one made on a plan's
    Razorpay payment page. Credit the account whose email was entered there,
    exactly once per Razorpay payment id."""
    payment_id = str(entity.get("id") or "")
    if not payment_id:
        return
    if session.query(Payment).filter_by(razorpay_payment_id=payment_id).first():
        return  # already credited (Razorpay retries webhooks)
    email = str(entity.get("email") or "").strip().lower()
    user = auth_service.get_by_email(email) if email else None
    # Test page amounts (INR 1) only ever match for an admin's own account.
    plan_id = _page_plan_for(entity.get("amount"), entity.get("currency"), admin=bool(user and user.is_admin))
    if plan_id is None:
        logger.warning(
            "Razorpay page payment %s (%s %s paise, email %r) matches no plan price; nothing credited -- review by hand",
            payment_id, entity.get("currency"), entity.get("amount"), email,
        )
        return
    if user is None:
        logger.warning(
            "Razorpay page payment %s for plan %s has no matching account (email %r); credit it by hand",
            payment_id, plan_id, email,
        )
        return
    payment = Payment(user_id=user.id, plan_id=plan_id, amount=entity["amount"], currency=entity["currency"],
                      razorpay_order_id=str(entity.get("order_id") or f"page_{payment_id}"))
    session.add(payment)
    session.commit()
    if _mark_paid(session, payment, payment_id):
        _credit_for_payment(payment)


@router.post("/webhook")
async def webhook(request: Request) -> dict:
    secrets = _webhook_secrets()
    if not secrets:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Webhook is not configured.")
    body = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")
    if not any(hmac.compare_digest(hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(), signature) for secret in secrets):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook signature.")
    payload = await request.json()
    if payload.get("event") == "payment.captured":
        entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        session = get_session()
        try:
            payment = session.query(Payment).filter_by(razorpay_order_id=entity.get("order_id")).first()
            if payment and entity.get("amount") == payment.amount and entity.get("currency") == payment.currency:
                if _mark_paid(session, payment, entity.get("id")):
                    _credit_for_payment(payment)
            elif payment is None:
                _credit_payment_page(session, entity)
        finally:
            session.close()
    return {"ok": True}
