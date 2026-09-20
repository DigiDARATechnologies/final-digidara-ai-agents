import hashlib
import hmac
import os
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import update

from app.auth import service as auth_service
from app.auth.security import get_current_user_id
from app.billing import invoice as invoice_pdf
from app.billing.plans import (
    PLANS,
    TOKENS_PER_RUPEE,
    active_plan,
    custom_plan,
    offered_plans,
    payment_label,
    plan_name,
    tokens_for_plan_id,
)
from app.db import get_session
from app.models import Payment

router = APIRouter(prefix="/billing", tags=["billing"])


class OrderRequest(BaseModel):
    plan_id: str


class TopupOrderRequest(BaseModel):
    amount_inr: int


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
    credit.
    """
    result = session.execute(
        update(Payment)
        .where(Payment.id == payment.id, Payment.status != "paid")
        .values(status="paid", razorpay_payment_id=razorpay_payment_id, paid_at=datetime.utcnow())
    )
    session.commit()
    return result.rowcount == 1


def _credit_for_payment(payment: Payment) -> None:
    tokens = tokens_for_plan_id(payment.plan_id)
    if tokens:
        auth_service.credit_tokens(payment.user_id, tokens)


@router.get("/plans")
def plans() -> dict:
    """The plans on sale, so prices live in one place (app/billing/plans.py)."""
    return {"plans": offered_plans(), "custom": custom_plan()}


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
    return {"balance": user.token_balance}


@router.post("/orders", status_code=201)
def create_order(req: OrderRequest, user_id: str = Depends(get_current_user_id)) -> dict:
    plan = PLANS.get(req.plan_id)
    if not plan:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown billing plan.")
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


@router.post("/topup-order", status_code=201)
def create_topup_order(req: TopupOrderRequest, user_id: str = Depends(get_current_user_id)) -> dict:
    if req.amount_inr < 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Minimum top-up amount is ₹1.")
    tokens = req.amount_inr * TOKENS_PER_RUPEE
    amount_paise = req.amount_inr * 100  # Razorpay amounts are in the smallest currency unit.
    plan_id = f"topup_{tokens}"
    key_id, key_secret = _credentials()
    receipt = f"dd_topup_{user_id[:10]}_{int(datetime.utcnow().timestamp())}"
    try:
        response = httpx.post("https://api.razorpay.com/v1/orders", auth=(key_id, key_secret), json={"amount": amount_paise, "currency": "INR", "receipt": receipt, "notes": {"user_id": user_id, "plan_id": plan_id, "tokens": tokens}}, timeout=15)
        response.raise_for_status()
        order = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Unable to create payment order.") from exc
    session = get_session()
    try:
        payment = Payment(user_id=user_id, plan_id=plan_id, amount=amount_paise, currency="INR", razorpay_order_id=order["id"])
        session.add(payment)
        session.commit()
    finally:
        session.close()
    return {"key_id": key_id, "order_id": order["id"], "amount": amount_paise, "currency": "INR", "name": f"{tokens:,} tokens", "tokens": tokens}


@router.post("/verify")
def verify_payment(req: VerifyRequest, user_id: str = Depends(get_current_user_id)) -> dict:
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


@router.post("/webhook")
async def webhook(request: Request) -> dict:
    secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Webhook is not configured.")
    body = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
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
        finally:
            session.close()
    return {"ok": True}
