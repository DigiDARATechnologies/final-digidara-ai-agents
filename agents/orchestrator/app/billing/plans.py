"""The billing plan catalog: the single source of truth for what is sold.

Tokens are the only thing that actually gates usage (there is no per-user
entitlement system), so every paid plan is a one-time payment that credits a
fixed number of tokens, at the same instant a verified top-up would. Prices
and token amounts live only here; the API serves them to the frontend so
nothing is hardcoded twice.

Change the numbers below to change pricing. Amounts are in paise (Razorpay's
smallest unit), so 49900 = INR 499.00.
"""
from datetime import datetime, timedelta

# Rupees paid -> tokens credited for a custom amount. INR 1 = 1,000 tokens.
TOKENS_PER_RUPEE = 1000

# A paid plan is shown as "active" for this long after payment. Plans are
# one-time payments, not auto-renewing subscriptions.
PLAN_PERIOD_DAYS = 30

PLANS: dict[str, dict] = {
    "basic": {
        "name": "Basic",
        "amount": 49900,
        "currency": "INR",
        "tokens": 500_000,
        "description": "For getting started and light, occasional use.",
    },
    "standard": {
        "name": "Standard",
        "amount": 99900,
        "currency": "INR",
        "tokens": 1_200_000,
        "description": "For regular learners who use several agents each week.",
        "popular": True,
    },
    "premium": {
        "name": "Premium",
        "amount": 199900,
        "currency": "INR",
        "tokens": 2_600_000,
        "description": "For heavy daily use across every agent.",
    },
}

# Sold before token plans existed. Not offered any more, but old payments must
# keep a proper name and a paying customer must not silently lose their
# "active plan" status. They never credited tokens and still do not.
LEGACY_PLANS: dict[str, dict] = {
    "pro_monthly": {"name": "Pro Monthly", "period_days": 30},
    "pro_yearly": {"name": "Pro Annual", "period_days": 365},
}


def bonus_percent(plan: dict) -> int:
    """How many percent more tokens the plan gives than a plain top-up of the same price."""
    baseline = plan["amount"] / 100 * TOKENS_PER_RUPEE
    return max(0, round((plan["tokens"] / baseline - 1) * 100))


def offered_plans() -> list[dict]:
    """The catalog as the API returns it, in display order."""
    result = []
    for plan_id, plan in PLANS.items():
        bonus = bonus_percent(plan)
        features = [
            f"{plan['tokens']:,} tokens credited instantly",
            "Tokens never expire",
            "Works across every agent",
        ]
        if bonus >= 1:
            features.insert(1, f"{bonus}% more tokens than a top-up of the same price")
        result.append({
            "id": plan_id,
            "name": plan["name"],
            "amount": plan["amount"],
            "currency": plan["currency"],
            "period": "month",
            "tokens": plan["tokens"],
            "bonus_percent": bonus,
            "description": plan["description"],
            "features": features,
            "popular": bool(plan.get("popular")),
        })
    return result


def custom_plan() -> dict:
    return {
        "id": "custom",
        "name": "Custom",
        "description": "Choose your own amount and pay only for what you need.",
        "tokens_per_rupee": TOKENS_PER_RUPEE,
        "min_amount_inr": 1,
    }


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
        tokens = tokens_for_plan_id(plan_id)
        return f"Token top-up ({tokens:,} tokens)" if tokens else "Token top-up"
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
