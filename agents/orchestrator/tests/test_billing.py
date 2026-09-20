"""Billing: plan catalog, payment labels, exactly-once token credit, invoices."""
import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from reportlab import rl_config

from app.auth import service as auth_service
from app.auth.security import get_current_user_id
from app.auth.service import create_user
from app.billing import invoice as invoice_pdf
from app.billing import plans as plan_catalog
from app.billing import routes as billing
from app.models import Payment

KEY_ID, KEY_SECRET = "rzp_test_key", "rzp_test_secret"


@pytest.fixture
def env(database, monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", KEY_ID)
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", KEY_SECRET)
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "hook-secret")
    monkeypatch.setattr(billing, "get_session", database)
    user = create_user("Asha Rao", "asha@example.com", "9999999999", "hash", "2026-01")
    other = create_user("Ravi K", "ravi@example.com", None, "hash", "2026-01")
    current = {"id": user.id}
    app = FastAPI()
    app.include_router(billing.router)
    app.dependency_overrides[get_current_user_id] = lambda: current["id"]
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, database=database, user=user, other=other, current=current)


def add_payment(env, plan_id, *, status="paid", user=None, amount=99900, paid_days_ago=0, order="order_1", payment_id=None):
    session = env.database()
    try:
        payment = Payment(
            user_id=(user or env.user).id, plan_id=plan_id, amount=amount, currency="INR", razorpay_order_id=order,
            razorpay_payment_id=payment_id, status=status,
            paid_at=datetime.utcnow() - timedelta(days=paid_days_ago) if status == "paid" else None,
        )
        session.add(payment)
        session.commit()
        return payment.id
    finally:
        session.close()


def balance(env, user=None):
    return auth_service.get_by_id((user or env.user).id).token_balance


def razorpay_ok(monkeypatch, order_id="order_1"):
    class Reply:
        def __init__(self, data):
            self.data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    calls = {"orders": []}

    def post(url, **kwargs):
        calls["orders"].append(kwargs["json"])
        return Reply({"id": order_id})

    monkeypatch.setattr(billing.httpx, "post", post)
    return calls


def captured(monkeypatch, order_id, amount, payment_id="pay_1"):
    class Reply:
        def raise_for_status(self):
            pass

        def json(self):
            return {"order_id": order_id, "amount": amount, "currency": "INR", "status": "captured", "id": payment_id}

    monkeypatch.setattr(billing.httpx, "get", lambda *a, **k: Reply())


def signature(order_id, payment_id):
    return hmac.new(KEY_SECRET.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


# --- catalog ---------------------------------------------------------------

def test_catalog_has_basic_standard_premium_and_a_custom_plan(env):
    body = env.client.get("/billing/plans").json()
    offered = {plan["id"]: plan for plan in body["plans"]}
    assert list(offered) == ["basic", "standard", "premium"]
    assert [offered[i]["amount"] for i in offered] == [49900, 99900, 199900]
    assert [offered[i]["tokens"] for i in offered] == [500_000, 1_200_000, 2_600_000]
    assert [offered[i]["bonus_percent"] for i in offered] == [0, 20, 30]
    assert [i for i in offered if offered[i]["popular"]] == ["standard"]
    assert body["custom"]["id"] == "custom" and body["custom"]["tokens_per_rupee"] == 1000
    assert "pro_monthly" not in offered and "pro_yearly" not in offered


def test_higher_plans_never_give_fewer_tokens_per_rupee(env):
    rates = [plan["tokens"] / plan["amount"] for plan in env.client.get("/billing/plans").json()["plans"]]
    assert rates == sorted(rates)


# --- labels and current plan ----------------------------------------------

def test_history_labels_distinguish_plans_topups_and_legacy_plans(env):
    add_payment(env, "topup_10000", amount=1000, order="o1")
    add_payment(env, "standard", order="o2")
    add_payment(env, "pro_monthly", order="o3")
    labels = {p["plan_id"]: p["label"] for p in env.client.get("/billing/summary").json()["payments"]}
    assert labels == {"topup_10000": "Token top-up (10,000 tokens)", "standard": "Standard plan", "pro_monthly": "Pro Monthly"}


def test_a_token_topup_does_not_make_you_a_plan_holder(env):
    add_payment(env, "topup_1000000", amount=100000)
    body = env.client.get("/billing/summary").json()
    assert body["plan"] == "free" and body["plan_name"] == "Free" and body["plan_expires_at"] is None


def test_a_paid_plan_is_active_for_thirty_days_then_lapses(env):
    add_payment(env, "premium", amount=199900, paid_days_ago=5, order="o1")
    body = env.client.get("/billing/summary").json()
    assert (body["plan"], body["plan_name"]) == ("premium", "Premium") and body["plan_expires_at"]

    lapsed = add_payment(env, "basic", amount=49900, paid_days_ago=40, order="o2", user=env.other)
    assert lapsed
    env.current["id"] = env.other.id
    assert env.client.get("/billing/summary").json()["plan"] == "free"


def test_unpaid_plans_do_not_count(env):
    add_payment(env, "premium", status="created")
    assert env.client.get("/billing/summary").json()["plan"] == "free"


def test_a_recent_legacy_pro_plan_keeps_its_active_status(env):
    add_payment(env, "pro_yearly", amount=999900, paid_days_ago=100)
    body = env.client.get("/billing/summary").json()
    assert (body["plan"], body["plan_name"]) == ("pro_yearly", "Pro Annual")


# --- ordering ---------------------------------------------------------------

def test_ordering_a_plan_charges_the_catalog_price(env, monkeypatch):
    calls = razorpay_ok(monkeypatch)
    body = env.client.post("/billing/orders", json={"plan_id": "standard"}).json()
    assert calls["orders"][0]["amount"] == 99900 and calls["orders"][0]["currency"] == "INR"
    assert body["amount"] == 99900 and body["name"] == "Standard plan"


@pytest.mark.parametrize("plan_id", ["pro_monthly", "pro_yearly", "custom", "gold", ""])
def test_plans_that_are_not_on_sale_cannot_be_ordered(env, monkeypatch, plan_id):
    calls = razorpay_ok(monkeypatch)
    assert env.client.post("/billing/orders", json={"plan_id": plan_id}).status_code == 400
    assert calls["orders"] == []


# --- crediting --------------------------------------------------------------

def test_verifying_a_plan_payment_credits_its_tokens_exactly_once(env, monkeypatch):
    add_payment(env, "standard", status="created", order="order_1")
    captured(monkeypatch, "order_1", 99900)
    before = balance(env)
    body = {"razorpay_order_id": "order_1", "razorpay_payment_id": "pay_1", "razorpay_signature": signature("order_1", "pay_1")}
    assert env.client.post("/billing/verify", json=body).json() == {"verified": True, "plan": "standard"}
    assert env.client.post("/billing/verify", json=body).status_code == 200  # client retry
    assert balance(env) == before + 1_200_000


def test_a_custom_topup_still_credits_the_rupee_rate(env, monkeypatch):
    add_payment(env, "topup_500000", status="created", amount=50000, order="order_1")
    captured(monkeypatch, "order_1", 50000)
    before = balance(env)
    body = {"razorpay_order_id": "order_1", "razorpay_payment_id": "pay_1", "razorpay_signature": signature("order_1", "pay_1")}
    env.client.post("/billing/verify", json=body)
    assert balance(env) == before + 500_000


def test_verify_and_the_webhook_together_credit_only_once(env, monkeypatch):
    add_payment(env, "premium", status="created", amount=199900, order="order_1")
    captured(monkeypatch, "order_1", 199900)
    before = balance(env)
    body = {"razorpay_order_id": "order_1", "razorpay_payment_id": "pay_1", "razorpay_signature": signature("order_1", "pay_1")}
    env.client.post("/billing/verify", json=body)
    event = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_1", "order_id": "order_1", "amount": 199900, "currency": "INR"}}}}).encode()
    hook = hmac.new(b"hook-secret", event, hashlib.sha256).hexdigest()
    assert env.client.post("/billing/webhook", content=event, headers={"x-razorpay-signature": hook}).status_code == 200
    assert balance(env) == before + 2_600_000


def test_only_the_first_mark_paid_call_wins(env):
    payment_id = add_payment(env, "basic", status="created", amount=49900, order="order_1")
    session = env.database()
    try:
        payment = session.get(Payment, payment_id)
        assert billing._mark_paid(session, payment, "pay_1") is True
        assert billing._mark_paid(session, payment, "pay_1") is False
    finally:
        session.close()


def test_a_wrong_signature_credits_nothing(env, monkeypatch):
    add_payment(env, "standard", status="created", order="order_1")
    captured(monkeypatch, "order_1", 99900)
    before = balance(env)
    body = {"razorpay_order_id": "order_1", "razorpay_payment_id": "pay_1", "razorpay_signature": "0" * 64}
    assert env.client.post("/billing/verify", json=body).status_code == 400
    assert balance(env) == before


# --- invoices ---------------------------------------------------------------

def test_a_paid_payment_downloads_as_a_pdf_invoice(env, monkeypatch):
    monkeypatch.setattr(rl_config, "pageCompression", 0)  # readable text in the assertions below
    payment_id = add_payment(env, "standard", payment_id="pay_abc123", order="order_xyz")
    response = env.client.get(f"/billing/invoices/{payment_id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert re.fullmatch(r'attachment; filename="DD-\d{6}-[A-Z0-9]{8}\.pdf"', response.headers["content-disposition"])
    pdf = response.content
    assert pdf.startswith(b"%PDF")
    for text in (b"Standard plan", b"INR 999.00", b"Asha Rao", b"asha@example.com", b"pay_abc123", b"order_xyz"):
        assert text in pdf, text


def test_an_invoice_shows_included_gst_only_when_configured(env, monkeypatch):
    monkeypatch.setattr(rl_config, "pageCompression", 0)
    payment_id = add_payment(env, "standard")
    assert b"GST" not in env.client.get(f"/billing/invoices/{payment_id}").content

    monkeypatch.setenv("INVOICE_GST_RATE", "18")
    monkeypatch.setenv("INVOICE_GSTIN", "29ABCDE1234F1Z5")
    monkeypatch.setenv("INVOICE_COMPANY_NAME", "DigiDARA Technologies")
    pdf = env.client.get(f"/billing/invoices/{payment_id}").content
    for text in (rb"GST @ 18% \(included\)", b"INR 846.61", b"INR 152.39", b"29ABCDE1234F1Z5", b"DigiDARA Technologies"):
        assert text in pdf, text


def test_an_unpaid_payment_has_no_invoice(env):
    payment_id = add_payment(env, "standard", status="created")
    assert env.client.get(f"/billing/invoices/{payment_id}").status_code == 409


def test_you_cannot_download_someone_elses_invoice(env):
    payment_id = add_payment(env, "standard", user=env.other)
    assert env.client.get(f"/billing/invoices/{payment_id}").status_code == 404
    assert env.client.get("/billing/invoices/does-not-exist").status_code == 404


def test_the_invoice_number_is_stable_and_derived_from_the_payment():
    when = datetime(2026, 9, 19, 10, 0)
    assert invoice_pdf.invoice_number("abcdef1234567890", when) == "DD-202609-ABCDEF12"


def test_catalog_helpers():
    assert plan_catalog.payment_label("topup_bad") == "Token top-up"
    assert plan_catalog.payment_label("mystery") == "mystery"
    assert plan_catalog.tokens_for_plan_id("pro_monthly") is None
    assert plan_catalog.tokens_for_plan_id("topup_1234") == 1234
