"""Core expense-tracking logic: validation and summaries."""
from collections import defaultdict
from datetime import date

CATEGORIES = ("Food", "Transport", "Bills", "Shopping", "Health", "Other")


def add_expense(expenses, amount, category, note="", when=None):
    """Validate and append one expense; returns the new record.

    Raises ValueError for a non-positive amount or an unknown category so bad
    data never reaches the saved file.
    """
    amount = round(float(amount), 2)
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    if category not in CATEGORIES:
        raise ValueError(f"Category must be one of: {', '.join(CATEGORIES)}.")
    record = {
        "date": (when or date.today()).isoformat(),
        "amount": amount,
        "category": category,
        "note": note.strip(),
    }
    expenses.append(record)
    return record


def total_by_category(expenses):
    """Return {category: total}, largest first."""
    totals = defaultdict(float)
    for item in expenses:
        totals[item["category"]] += item["amount"]
    return dict(sorted(((k, round(v, 2)) for k, v in totals.items()), key=lambda pair: -pair[1]))


def monthly_total(expenses, year, month):
    """Sum of all expenses dated in the given month."""
    prefix = f"{year:04d}-{month:02d}"
    return round(sum(item["amount"] for item in expenses if item["date"].startswith(prefix)), 2)
