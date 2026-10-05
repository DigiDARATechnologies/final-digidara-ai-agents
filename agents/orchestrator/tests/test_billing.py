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
from app.rate_limit import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

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
    limiter.reset()                      # /orders and /verify are rate limited per caller
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
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

def test_catalog_is_399_799_and_999_with_no_custom_plan(env):
    body = env.client.get("/billing/plans").json()
    offered = {plan["id"]: plan for plan in body["plans"]}
    assert list(offered) == ["basic", "standard", "premium"]
    assert [offered[i]["amount"] for i in offered] == [39900, 79900, 99900]
    assert [i for i in offered if offered[i]["popular"]] == ["standard"]
    assert "custom" not in body
    assert "pro_monthly" not in offered and "pro_yearly" not in offered
    # Only the 999 plan is paid on the Razorpay payment page.
    assert [i for i in offered if offered[i]["payment_page_url"]] == ["premium"]
    assert offered["premium"]["payment_page_url"] == "https://rzp.io/rzp/j6YPZzy8"


def test_plans_sell_fixed_tokens_shown_as_points():
    assert [(plan_catalog.PLANS[i]["tokens"], plan_catalog.PLANS[i]["points"]) for i in ("basic", "standard", "premium")] == [
        (500_000, 250), (1_000_000, 500), (1_500_000, 750),
    ]
    # Off-price payments are still priced at gpt-4o-mini's rate: $0.15 in /
    # $0.60 out per million, blended 3:1, at INR 96.25 per USD.
    assert plan_catalog.inr_per_million_tokens() == pytest.approx(25.265625)


def test_an_order_paid_at_an_older_price_gets_what_it_paid_for():
    assert plan_catalog.tokens_for_payment("basic", 39900) == plan_catalog.PLANS["basic"]["tokens"]
    assert plan_catalog.tokens_for_payment("basic", 49900) == 500_000        # the old Basic price bought 500,000
    # Any other amount gets the plan's own tokens scaled to it -- never
    # OpenAI's raw per-rupee rate, which is ~30x what a plan gives.
    assert plan_catalog.tokens_for_payment("basic", 45000) == round(500_000 * 45000 / 39900)
    assert plan_catalog.points_for_payment("basic", 45000) == round(250 * 45000 / 39900, 2)
    assert plan_catalog.points_for_payment("basic", 49900) is None          # an old-price order: it sold tokens, not points
    assert plan_catalog.tokens_for_payment("topup_500000", 50000) == 500_000


def test_higher_plans_never_give_meaningfully_fewer_points_per_rupee(env):
    # 250 / 399 and 500 / 799 are the same rate to within a rounding paisa.
    rates = [plan["points"] / plan["amount"] for plan in env.client.get("/billing/plans").json()["plans"]]
    assert all(later >= earlier * 0.995 for earlier, later in zip(rates, rates[1:]))


# --- labels and current plan ----------------------------------------------

def test_history_labels_distinguish_plans_topups_and_legacy_plans(env):
    add_payment(env, "topup_10000", amount=1000, order="o1")
    add_payment(env, "standard", order="o2")
    add_payment(env, "pro_monthly", order="o3")
    labels = {p["plan_id"]: p["label"] for p in env.client.get("/billing/summary").json()["payments"]}
    assert labels == {"topup_10000": "Points top-up", "standard": "Standard plan", "pro_monthly": "Pro Monthly"}


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
    assert calls["orders"][0]["amount"] == 79900 and calls["orders"][0]["currency"] == "INR"
    assert body["amount"] == 79900 and body["name"] == "Standard plan"


@pytest.mark.parametrize("plan_id", ["pro_monthly", "pro_yearly", "custom", "gold", "", "premium"])
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
    add_payment(env, "standard", status="created", amount=79900, order="order_1")
    captured(monkeypatch, "order_1", 79900)
    before = balance(env)
    body = {"razorpay_order_id": "order_1", "razorpay_payment_id": "pay_1", "razorpay_signature": signature("order_1", "pay_1")}
    env.client.post("/billing/verify", json=body)
    event = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_1", "order_id": "order_1", "amount": 79900, "currency": "INR"}}}}).encode()
    hook = hmac.new(b"hook-secret", event, hashlib.sha256).hexdigest()
    assert env.client.post("/billing/webhook", content=event, headers={"x-razorpay-signature": hook}).status_code == 200
    assert balance(env) == before + plan_catalog.PLANS["standard"]["tokens"]


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
    assert plan_catalog.payment_label("topup_bad") == "Points top-up"
    assert plan_catalog.payment_label("mystery") == "mystery"
    assert plan_catalog.tokens_for_plan_id("pro_monthly") is None
    assert plan_catalog.tokens_for_plan_id("topup_1234") == 1234


def add_usage(env, tokens, *, agent="certificate_agent", user=None, days_ago=0, at=None):
    from app.models import TokenUsageEvent
    session = env.database()
    try:
        session.add(TokenUsageEvent(user_id=(user or env.user).id, agent_name=agent, action="x", tokens=tokens,
                                    created_at=at or datetime.utcnow() - timedelta(days=days_ago)))
        session.commit()
    finally:
        session.close()


def test_a_new_user_has_no_usage_this_month_and_their_balance_is_the_limit(env):
    body = env.client.get("/billing/usage-month").json()
    assert (body["tokens_used"], body["requests"], body["agents"]) == (0, 0, [])
    assert body["limit"] == body["balance"] == balance(env)


def test_usage_this_month_counts_only_this_user_and_this_month(env, monkeypatch):
    monkeypatch.setattr(billing, "month_start_utc", lambda now, offset: datetime.utcnow() - timedelta(days=5))
    add_usage(env, 300)
    add_usage(env, 200)
    add_usage(env, 50, agent="mock_interview_agent")
    add_usage(env, 9999, days_ago=10)            # last month
    add_usage(env, 7777, user=env.other)         # someone else
    body = env.client.get("/billing/usage-month").json()
    assert (body["tokens_used"], body["requests"]) == (550, 3)
    assert sorted((a["agent_name"], a["tokens"], a["requests"]) for a in body["agents"]) == [
        ("certificate_agent", 500, 2), ("mock_interview_agent", 50, 1)]
    # The limit is dynamic: this month's usage plus what is left to spend.
    assert body["limit"] == 550 + balance(env)


def test_the_limit_never_counts_a_negative_balance(env):
    auth_service.settle_tokens(env.user.id, balance(env) + 40, "certificate_agent", "send_chat_message")
    body = env.client.get("/billing/usage-month").json()
    assert body["balance"] == 0 and body["limit"] == body["tokens_used"]


def test_the_month_turns_over_at_the_users_midnight():
    # 1 Oct 01:00 IST is still 30 Sep in UTC; for an IST user that is October.
    now = datetime(2026, 9, 30, 19, 30)
    assert billing.month_start_utc(now, 330) == datetime(2026, 9, 30, 18, 30)
    assert billing.month_start_utc(now, 0) == datetime(2026, 9, 1)


# --- the 999 plan's Razorpay payment page ----------------------------------

def page_payment(env, payment_id="pay_page_1", email="ASHA@example.com", amount=99900, secret=b"hook-secret"):
    event = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {
        "id": payment_id, "order_id": f"order_{payment_id}", "amount": amount, "currency": "INR", "email": email}}}}).encode()
    return env.client.post("/billing/webhook", content=event,
                           headers={"x-razorpay-signature": hmac.new(secret, event, hashlib.sha256).hexdigest()})


def test_the_999_page_charges_gst_and_still_credits_exactly_the_999_plan(env):
    # The Razorpay page charges INR 999 + 18% GST = INR 1,178.82.
    set_balance(env, 0)
    assert page_payment(env, amount=117882).status_code == 200
    assert balance(env) == 1_500_000 and points(env) == 750
    payment = env.client.get("/billing/summary").json()["payments"][0]
    assert (payment["plan_id"], payment["amount"], payment["points"]) == ("premium", 117882, 750)


def test_a_999_payment_page_payment_credits_the_account_with_that_email(env):
    before = balance(env)
    assert page_payment(env).status_code == 200
    assert balance(env) == before + plan_catalog.PLANS["premium"]["tokens"]
    summary = env.client.get("/billing/summary").json()
    assert (summary["plan"], summary["payments"][0]["status"], summary["payments"][0]["payment_id"]) == ("premium", "paid", "pay_page_1")


def test_a_retried_page_webhook_credits_only_once(env):
    before = balance(env)
    page_payment(env)
    page_payment(env)
    assert balance(env) == before + plan_catalog.PLANS["premium"]["tokens"]


def test_a_page_payment_with_an_unknown_email_credits_nobody(env):
    before = (balance(env), balance(env, env.other))
    assert page_payment(env, email="stranger@example.com").status_code == 200
    assert (balance(env), balance(env, env.other)) == before


def test_a_captured_payment_of_another_amount_is_not_treated_as_the_999_plan(env):
    before = balance(env)
    page_payment(env, amount=50000)
    assert balance(env) == before


def test_the_payment_page_can_sign_with_its_own_webhook_secret(env, monkeypatch):
    monkeypatch.setenv("RAZORPAY_PAGE_WEBHOOK_SECRET", "page-secret")
    before = balance(env)
    assert page_payment(env, secret=b"page-secret").status_code == 200
    assert balance(env) == before + plan_catalog.PLANS["premium"]["tokens"]
    assert page_payment(env, payment_id="pay_page_2", secret=b"wrong").status_code == 400


def test_the_999_plan_cannot_be_ordered_in_app(env, monkeypatch):
    razorpay_ok(monkeypatch)
    assert env.client.post("/billing/orders", json={"plan_id": "premium"}).status_code == 400


# --- points ----------------------------------------------------------------

def set_balance(env, tokens, tokens_per_point=None, user=None):
    from app.models import User
    session = env.database()
    try:
        row = session.get(User, (user or env.user).id)
        row.token_balance = tokens
        if tokens_per_point is not None:
            row.tokens_per_point = tokens_per_point
        session.commit()
    finally:
        session.close()


def points(env):
    return env.client.get("/billing/token-balance").json()["points"]


def buy(env, monkeypatch, plan_id, order):
    amount = plan_catalog.PLANS[plan_id]["amount"]
    add_payment(env, plan_id, status="created", amount=amount, order=order)
    captured(monkeypatch, order, amount, payment_id="pay_" + order)
    body = {"razorpay_order_id": order, "razorpay_payment_id": "pay_" + order, "razorpay_signature": signature(order, "pay_" + order)}
    assert env.client.post("/billing/verify", json=body).status_code == 200


def test_a_new_account_starts_with_the_free_points(env):
    assert points(env) == plan_catalog.FREE_SIGNUP_POINTS
    assert balance(env) == plan_catalog.free_signup_tokens()


@pytest.mark.parametrize("plan_id,shown", [("basic", 250), ("standard", 500), ("premium", 750)])
def test_each_plan_shows_its_own_points(env, monkeypatch, plan_id, shown):
    set_balance(env, 0)
    buy(env, monkeypatch, plan_id, "order_1")
    assert balance(env) == plan_catalog.PLANS[plan_id]["tokens"]
    assert points(env) == shown


def test_points_add_up_across_plans_with_different_rates(env, monkeypatch):
    set_balance(env, 0)
    buy(env, monkeypatch, "basic", "order_1")        # 500,000 tokens as 250 points
    buy(env, monkeypatch, "premium", "order_2")      # 1,500,000 tokens as 750 points
    assert balance(env) == 2_000_000 and points(env) == 1000


def test_free_points_and_a_plan_add_up(env, monkeypatch):
    buy(env, monkeypatch, "basic", "order_1")
    assert points(env) == plan_catalog.FREE_SIGNUP_POINTS + 250


def test_spending_tokens_spends_points_at_the_accounts_rate(env, monkeypatch):
    set_balance(env, 0)
    buy(env, monkeypatch, "basic", "order_1")        # 2,000 tokens a point
    auth_service.settle_tokens(env.user.id, 15_000, "aptitude_agent", "create_test")
    assert points(env) == 242.5


def test_a_negative_balance_still_shows_the_points_just_bought(env, monkeypatch):
    set_balance(env, -2_000)
    buy(env, monkeypatch, "standard", "order_1")
    assert balance(env) == 998_000 and points(env) == 500


def test_an_old_balance_keeps_the_rate_stored_on_its_row(env):
    # Rows from before 6 Oct 2026 were migrated at 3,000 tokens a point.
    set_balance(env, 120_000, tokens_per_point=plan_catalog.LEGACY_TOKENS_PER_POINT)
    assert points(env) == 40


def test_monthly_usage_reports_points(env, monkeypatch):
    set_balance(env, 0)
    buy(env, monkeypatch, "basic", "order_1")
    auth_service.settle_tokens(env.user.id, 30_000, "aptitude_agent", "create_test")   # also records the usage
    body = env.client.get("/billing/usage-month").json()
    assert body["points_used"] == 15 and body["points_balance"] == 235 and body["points_limit"] == 250
    assert [(a["agent_name"], a["points"]) for a in body["agents"]] == [("aptitude_agent", 15)]


def test_the_catalog_and_history_show_points(env):
    offered = {plan["id"]: plan for plan in env.client.get("/billing/plans").json()["plans"]}
    assert [offered[i]["points"] for i in ("basic", "standard", "premium")] == [250, 500, 750]
    assert offered["basic"]["features"][0] == "250 points credited instantly"
    assert not any("token" in feature.lower() for plan in offered.values() for feature in plan["features"])
    add_payment(env, "premium", order="o1")
    assert env.client.get("/billing/summary").json()["payments"][0]["points"] == 750


# --- crediting is recorded and server-side only ------------------------------

def test_a_paid_payment_records_what_it_credited_and_a_later_price_change_cannot_rewrite_it(env, monkeypatch):
    set_balance(env, 0)
    buy(env, monkeypatch, "basic", "order_1")
    session = env.database()
    try:
        row = session.query(Payment).filter_by(razorpay_order_id="order_1").one()
        assert (row.credited_tokens, row.credited_points) == (500_000, 250)
    finally:
        session.close()
    monkeypatch.setitem(plan_catalog.PLANS["basic"], "points", 1)       # the catalog changes later
    assert env.client.get("/billing/summary").json()["payments"][0]["points"] == 250


def test_order_creation_is_rate_limited_per_account(env, monkeypatch):
    made = iter(range(100))
    monkeypatch.setattr(billing.httpx, "post", lambda *a, **k: SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"id": f"order_{next(made)}"}))
    codes = [env.client.post("/billing/orders", json={"plan_id": "basic"}).status_code for _ in range(11)]
    assert codes[:10] == [201] * 10 and codes[10] == 429


def test_the_browser_cannot_choose_what_a_plan_credits(env, monkeypatch):
    # Only plan_id is accepted; amount and tokens come from the server's catalog.
    calls = razorpay_ok(monkeypatch)
    env.client.post("/billing/orders", json={"plan_id": "basic", "amount": 100, "tokens": 99_999_999, "points": 99_999})
    assert calls["orders"][0]["amount"] == 39900
