import os
from decimal import Decimal, InvalidOperation

from flask import current_app, has_app_context

GROQ_PRICING_SOURCE = "https://console.groq.com/docs/models"
GROQ_PRICING_EFFECTIVE_DATE = "2026-08-20"
GROQ_COST_CURRENCY = "USD"

# Source: Groq Supported Models page, PRICE PER 1M TOKENS table.
# If a configured model is not listed here, cost is intentionally unavailable.
GROQ_MODEL_PRICING = {
    "openai/gpt-oss-120b": {
        "input_per_1m": Decimal("0.15"),
        "output_per_1m": Decimal("0.60"),
        "currency": GROQ_COST_CURRENCY,
        "effective_date": GROQ_PRICING_EFFECTIVE_DATE,
        "source": GROQ_PRICING_SOURCE,
    },
    "openai/gpt-oss-20b": {
        "input_per_1m": Decimal("0.075"),
        "output_per_1m": Decimal("0.30"),
        "currency": GROQ_COST_CURRENCY,
        "effective_date": GROQ_PRICING_EFFECTIVE_DATE,
        "source": GROQ_PRICING_SOURCE,
    },
    "openai/gpt-oss-safeguard-20b": {
        "input_per_1m": Decimal("0.075"),
        "output_per_1m": Decimal("0.30"),
        "currency": GROQ_COST_CURRENCY,
        "effective_date": GROQ_PRICING_EFFECTIVE_DATE,
        "source": GROQ_PRICING_SOURCE,
    },
    "meta-llama/llama-prompt-guard-2-22m": {
        "input_per_1m": Decimal("0.03"),
        "output_per_1m": Decimal("0.03"),
        "currency": GROQ_COST_CURRENCY,
        "effective_date": GROQ_PRICING_EFFECTIVE_DATE,
        "source": GROQ_PRICING_SOURCE,
    },
    "meta-llama/llama-prompt-guard-2-86m": {
        "input_per_1m": Decimal("0.04"),
        "output_per_1m": Decimal("0.04"),
        "currency": GROQ_COST_CURRENCY,
        "effective_date": GROQ_PRICING_EFFECTIVE_DATE,
        "source": GROQ_PRICING_SOURCE,
    },
    "qwen/qwen3.6-27b": {
        "input_per_1m": Decimal("0.60"),
        "output_per_1m": Decimal("3.00"),
        "currency": GROQ_COST_CURRENCY,
        "effective_date": GROQ_PRICING_EFFECTIVE_DATE,
        "source": GROQ_PRICING_SOURCE,
    },
}


def _decimal_env(name):
    value = current_app.config.get(name) if has_app_context() else os.getenv(name)
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        if has_app_context():
            current_app.logger.warning("Ignoring invalid %s value for Groq pricing", name)
        return None


def _config_value(name, default=None):
    if has_app_context():
        return current_app.config.get(name) or default
    return os.getenv(name) or default


def pricing_for_model(model):
    override_input = _decimal_env("GROQ_INPUT_PRICE_PER_1M")
    if override_input is None:
        override_input = _decimal_env("GROQ_INPUT_COST_PER_1M")
    override_output = _decimal_env("GROQ_OUTPUT_PRICE_PER_1M")
    if override_output is None:
        override_output = _decimal_env("GROQ_OUTPUT_COST_PER_1M")
    if override_input is not None and override_output is not None:
        return {
            "input_per_1m": override_input,
            "output_per_1m": override_output,
            "currency": _config_value("GROQ_PRICE_CURRENCY", _config_value("GROQ_COST_CURRENCY", GROQ_COST_CURRENCY)),
            "effective_date": _config_value("GROQ_PRICING_EFFECTIVE_DATE", "env-override"),
            "source": _config_value("GROQ_PRICING_SOURCE", "environment"),
        }
    return GROQ_MODEL_PRICING.get(str(model or "").strip())


def estimate_cost(model, usage):
    if not usage or usage.get("usage_available") is False:
        return {
            "pricing_available": False,
            "reason": "usage_unavailable",
            "input_cost": None,
            "output_cost": None,
            "estimated_total_cost": None,
            "currency": _config_value("GROQ_PRICE_CURRENCY", _config_value("GROQ_COST_CURRENCY", GROQ_COST_CURRENCY)),
            "pricing_effective_date": None,
            "pricing_source": None,
        }

    pricing = pricing_for_model(model)
    if not pricing:
        return {
            "pricing_available": False,
            "reason": "model_pricing_not_configured",
            "input_cost": None,
            "output_cost": None,
            "estimated_total_cost": None,
            "currency": _config_value("GROQ_PRICE_CURRENCY", _config_value("GROQ_COST_CURRENCY", GROQ_COST_CURRENCY)),
            "pricing_effective_date": None,
            "pricing_source": None,
        }

    one_million = Decimal("1000000")
    input_tokens = Decimal(int(usage.get("input_tokens") or 0))
    output_tokens = Decimal(int(usage.get("output_tokens") or 0))
    input_cost = (input_tokens / one_million) * pricing["input_per_1m"]
    output_cost = (output_tokens / one_million) * pricing["output_per_1m"]
    return {
        "pricing_available": True,
        "reason": None,
        "input_cost": input_cost.quantize(Decimal("0.000000001")),
        "output_cost": output_cost.quantize(Decimal("0.000000001")),
        "estimated_total_cost": (input_cost + output_cost).quantize(Decimal("0.000000001")),
        "currency": pricing["currency"],
        "pricing_effective_date": pricing["effective_date"],
        "pricing_source": pricing["source"],
    }
