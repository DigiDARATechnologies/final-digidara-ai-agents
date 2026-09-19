import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from storage import load_expenses, save_expenses  # noqa: E402
from tracker import add_expense, monthly_total, total_by_category  # noqa: E402


def test_add_expense_records_a_clean_entry():
    expenses = []
    record = add_expense(expenses, "250", "Food", "  Lunch  ", when=date(2026, 9, 1))
    assert record == {"date": "2026-09-01", "amount": 250.0, "category": "Food", "note": "Lunch"}
    assert expenses == [record]


@pytest.mark.parametrize("amount", [0, -5])
def test_non_positive_amounts_are_rejected(amount):
    with pytest.raises(ValueError):
        add_expense([], amount, "Food")


def test_unknown_category_is_rejected():
    with pytest.raises(ValueError):
        add_expense([], 10, "Gadgets")


def test_totals_are_grouped_and_sorted_largest_first():
    expenses = []
    add_expense(expenses, 100, "Transport")
    add_expense(expenses, 250, "Food")
    add_expense(expenses, 50, "Food")
    assert total_by_category(expenses) == {"Food": 300.0, "Transport": 100.0}
    assert list(total_by_category(expenses)) == ["Food", "Transport"]


def test_monthly_total_only_counts_that_month():
    expenses = []
    add_expense(expenses, 100, "Bills", when=date(2026, 9, 3))
    add_expense(expenses, 40, "Bills", when=date(2026, 10, 3))
    assert monthly_total(expenses, 2026, 9) == 100.0


def test_expenses_survive_a_save_and_load(tmp_path):
    path = tmp_path / "expenses.json"
    expenses = []
    add_expense(expenses, 75.5, "Health", "Pharmacy", when=date(2026, 9, 2))
    save_expenses(expenses, path)
    assert load_expenses(path) == expenses
