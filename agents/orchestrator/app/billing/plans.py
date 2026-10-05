"""The billing plan catalog: the single source of truth for what is sold.

Tokens are the only thing that actually gates usage (there is no per-user
entitlement system), so every paid plan is a one-time payment that credits a
fixed number of tokens, at the same instant a verified top-up would. Prices
and token amounts live only here; the API serves them to the frontend so
nothing is hardcoded twice.

Users never see tokens: they see points. Each plan sells a fixed number of
points for its tokens, so each plan has its own tokens-per-point rate, and
every account stores the rate of what it holds (users.tokens_per_point; see
auth/service.py:credit_tokens for how a purchase blends it). Balance and
usage are always kept in tokens and only converted for display.

Change the numbers below to change pricing. Amounts are in paise (Razorpay's
smallest unit), so 49900 = INR 499.00.
"""
import os
from datetime import datetime, timedelta

# Rupees paid -> tokens credited for a legacy custom top-up (no longer sold;
# kept so old top-up payments still have a name and credit correctly).
TOKENS_PER_RUPEE = 1000

# Plans now sell fixed amounts (see PLANS). This OpenAI rate only prices a
# payment made at an amount no plan sells, at what that money buys from
# OpenAI at the rate of gpt-4o-mini, the model most agents run on (checked 1 Oct 2026):
# $0.15 per million input tokens and $0.60 per million output tokens,
# blended 3 input : 1 output (the usual blend), converted at ~INR 96.25 per
# USD. That is INR ~25.27 per million tokens. Override with the env vars
# below when OpenAI's price or the exchange rate moves.
OPENAI_INPUT_USD_PER_MILLION = float(os.getenv("OPENAI_INPUT_USD_PER_MILLION", "0.15"))
OPENAI_OUTPUT_USD_PER_MILLION = float(os.getenv("OPENAI_OUTPUT_USD_PER_MILLION", "0.60"))
OPENAI_INPUT_SHARE = float(os.getenv("OPENAI_INPUT_SHARE", "0.75"))
USD_TO_INR = float(os.getenv("USD_TO_INR", "96.25"))


def inr_per_million_tokens() -> float:
    usd = OPENAI_INPUT_SHARE * OPENAI_INPUT_USD_PER_MILLION + (1 - OPENAI_INPUT_SHARE) * OPENAI_OUTPUT_USD_PER_MILLION
    return usd * USD_TO_INR


def tokens_for_rupees(rupees: float) -> int:
    """What `rupees` buys from OpenAI, to the nearest thousand tokens."""
    return round(rupees / inr_per_million_tokens() * 1_000) * 1000

# A paid plan is shown as "active" for this long after payment. Plans are
# one-time payments, not auto-renewing subscriptions.
PLAN_PERIOD_DAYS = 30

PLANS: dict[str, dict] = {
    "basic": {
        "name": "Basic",
        "amount": 39900,
        "currency": "INR",
        "tokens": 500_000,
        "points": 250,
        "description": "For getting started and light, occasional use.",
    },
    "standard": {
        "name": "Standard",
        "amount": 79900,
        "currency": "INR",
        "tokens": 1_000_000,
        "points": 500,
        "description": "For regular learners who use several agents each week.",
        "popular": True,
        # Paid on DigiDARA's Razorpay payment page, like Premium below.
        "payment_page_url": os.getenv("RAZORPAY_STANDARD_PAGE_URL", "https://rzp.io/rzp/mKDSePpB"),
        # What that page charges: INR 799 + 18% GST = INR 942.82.
        "page_amount": int(os.getenv("RAZORPAY_STANDARD_PAGE_AMOUNT", "94282")),
    },
    "premium": {
        "name": "Premium",
        "amount": 99900,
        "currency": "INR",
        "tokens": 1_500_000,
        "points": 750,
        "description": "For heavy daily use across every agent.",
        # Paid on DigiDARA's own Razorpay payment page instead of the in-app
        # checkout; the webhook credits the account whose email was entered
        # there (routes.py `_credit_payment_page`).
        "payment_page_url": os.getenv("RAZORPAY_PREMIUM_PAGE_URL", "https://rzp.io/rzp/j6YPZzy8"),
        # What that page actually charges: INR 999 + 18% GST = INR 1,178.82.
        # The webhook only credits a page payment of exactly this amount (or
        # the plan price), so keep it in step with the page.
        "page_amount": int(os.getenv("RAZORPAY_PREMIUM_PAGE_AMOUNT", "117882")),
    },
}


def is_full_price(plan: dict, amount_paise: int) -> bool:
    """The plan's price, or what its Razorpay page charges (price + GST)."""
    return amount_paise in (plan["amount"], plan.get("page_amount"))


def exact_credit(plan_id: str, amount_paise: int, currency: str) -> tuple[int, int] | None:
    """The one place that decides what a payment credits: exactly the plan's
    tokens and points, and only for exactly its price -- INR 399 -> 500,000,
    INR 799 (or the INR 942.82 its Razorpay page charges with GST) ->
    1,000,000, INR 999 (or the INR 1,178.82 its page charges) -> 1,500,000.
    Never scaled, never rounded up.

    Anything else credits nothing: a different amount, a plan no longer sold,
    a legacy top-up, another currency. The caller logs it so a person can
    review it and credit by hand; an unexpected payment must never turn into
    tokens on its own.
    """
    plan = PLANS.get(plan_id)
    if plan is None or currency != plan["currency"] or not is_full_price(plan, amount_paise):
        return None
    return plan["tokens"], plan["points"]

# Every plan sells points at 2,000 tokens a point, and new free accounts use
# the same rate. (Accounts created before this kept the rate stored on their
# row, so their shown balance never jumps.) New accounts start with enough
# points to finish full flows in at least four agents (one Aptitude test, one
# mock interview, a Communication Coach session and a resume, say); tune with
# these env vars.
FREE_TOKENS_PER_POINT = float(os.getenv("FREE_TOKENS_PER_POINT", "2000"))
FREE_SIGNUP_POINTS = float(os.getenv("FREE_SIGNUP_POINTS", "100"))


# The rate every balance had before 6 Oct 2026 (stored on those users' rows
# by the migration), used to show pre-points payments as points.
LEGACY_TOKENS_PER_POINT = 3000.0


def credited_tokens(payment) -> int:
    """What a payment credited: as recorded when it was marked paid, else
    (payments from before that was recorded) from the catalog."""
    if payment.credited_tokens is not None:
        return payment.credited_tokens
    return tokens_for_payment(payment.plan_id, payment.amount) or 0


def credited_points(payment) -> float:
    """Points a payment credited, recorded like credited_tokens. Older
    payments are derived from the catalog, and ones that sold no points
    count at the rate balances had then."""
    if payment.credited_points is not None:
        return payment.credited_points
    sold = points_for_payment(payment.plan_id, payment.amount)
    return sold if sold is not None else points_for_tokens(credited_tokens(payment), LEGACY_TOKENS_PER_POINT)


def free_signup_tokens() -> int:
    return int(FREE_SIGNUP_POINTS * FREE_TOKENS_PER_POINT)


def points_for_tokens(tokens: float, tokens_per_point: float | None) -> float:
    """Tokens shown as points at an account's rate, to two decimals."""
    rate = tokens_per_point if tokens_per_point and tokens_per_point > 0 else FREE_TOKENS_PER_POINT
    return round(tokens / rate, 2)


def points_for_payment(plan_id: str, amount_paise: int) -> float | None:
    """The points a plan sells at exactly its price; None for any other
    amount or plan. For showing a payment -- crediting uses exact_credit."""
    plan = PLANS.get(plan_id)
    return plan["points"] if plan and is_full_price(plan, amount_paise) else None


# Sold before token plans existed. Not offered any more, but old payments must
# keep a proper name and a paying customer must not silently lose their
# "active plan" status. They never credited tokens and still do not.
LEGACY_PLANS: dict[str, dict] = {
    "pro_monthly": {"name": "Pro Monthly", "period_days": 30},
    "pro_yearly": {"name": "Pro Annual", "period_days": 365},
}


def bonus_percent(plan: dict) -> int:
    """How many percent more tokens the plan gives than OpenAI's own rate for its price."""
    baseline = tokens_for_rupees(plan["amount"] / 100)
    return max(0, round((plan["tokens"] / baseline - 1) * 100)) if baseline else 0


def offered_plans() -> list[dict]:
    """The catalog as the API returns it, in display order."""
    result = []
    for plan_id, plan in PLANS.items():
        bonus = bonus_percent(plan)
        page = plan.get("payment_page_url")
        features = [
            f"{plan['points']:,} points" + (" added after Razorpay confirms the payment" if page else " credited instantly"),
            "Points never expire",
            "Works across every agent",
        ]
        result.append({
            "id": plan_id,
            "name": plan["name"],
            "amount": plan["amount"],
            "currency": plan["currency"],
            "period": "month",
            "tokens": plan["tokens"],
            "points": plan["points"],
            "bonus_percent": bonus,
            "description": plan["description"],
            "features": features,
            "popular": bool(plan.get("popular")),
            "payment_page_url": page,
            "page_amount": plan.get("page_amount") if page else None,
        })
    return result


# Plans as sold before 1 Oct 2026: (plan id, price in paise) -> tokens. Old
# payments keep the tokens they actually bought (history, admin totals), and
# an order created at an old price but paid after the change gets those.
PREVIOUS_PLAN_TOKENS = {
    ("basic", 49900): 500_000,
    ("standard", 99900): 1_200_000,
    ("premium", 199900): 2_600_000,
}


def tokens_for_payment(plan_id: str, amount_paise: int) -> int | None:
    """What an old payment (paid before credits were recorded on the row)
    bought, for history and admin totals only: the plan's tokens at the
    price it was sold at then. Crediting uses exact_credit, never this."""
    if (plan_id, amount_paise) in PREVIOUS_PLAN_TOKENS:
        return PREVIOUS_PLAN_TOKENS[(plan_id, amount_paise)]
    plan = PLANS.get(plan_id)
    if plan and not is_full_price(plan, amount_paise):
        return None
    return tokens_for_plan_id(plan_id)


def tokens_for_plan_id(plan_id: str) -> int | None:
    """Tokens to credit for a paid payment, or None when it credits nothing."""
    if plan_id.startswith("topup_"):
        try:
            return int(plan_id.split("_", 1)[1])
        except (IndexError, ValueError):
            return None
    plan = PLANS.get(plan_id)
    return plan["tokens"] if plan else None


def payment_label(plan_id: str) -> str:
    """Human-readable name for a payment row, whatever kind of payment it was."""
    if plan_id.startswith("topup_"):
        return "Points top-up"
    if plan_id in PLANS:
        return f"{PLANS[plan_id]['name']} plan"
    if plan_id in LEGACY_PLANS:
        return LEGACY_PLANS[plan_id]["name"]
    return plan_id


def plan_period_days(plan_id: str) -> int | None:
    if plan_id in PLANS:
        return PLAN_PERIOD_DAYS
    if plan_id in LEGACY_PLANS:
        return LEGACY_PLANS[plan_id]["period_days"]
    return None


def plan_name(plan_id: str) -> str:
    if plan_id in PLANS:
        return PLANS[plan_id]["name"]
    if plan_id in LEGACY_PLANS:
        return LEGACY_PLANS[plan_id]["name"]
    return "Free"


def active_plan(paid_payments, now: datetime | None = None) -> tuple[str, datetime | None]:
    """The user's current plan from their paid payments, newest first.

    Only real plans count: a token top-up is not a plan, and a plan stops being
    active PLAN_PERIOD_DAYS after it was paid. Returns ("free", None) otherwise.
    """
    now = now or datetime.utcnow()
    for payment in paid_payments:
        days = plan_period_days(payment.plan_id)
        if days is None or payment.paid_at is None:
            continue
        expires = payment.paid_at + timedelta(days=days)
        if expires > now:
            return payment.plan_id, expires
    return "free", None
