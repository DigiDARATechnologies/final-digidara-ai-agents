"""Command-line entry point for the Expense Tracker.

    python src/main.py                      run a demo on the sample data
    python src/main.py add --amount 250 --category Food --note "Lunch"
    python src/main.py summary              totals per category
"""
import argparse
import sys
from pathlib import Path

from storage import DATA_DIR, DEFAULT_PATH, load_expenses, save_expenses
from tracker import CATEGORIES, add_expense, total_by_category

SAMPLE_PATH = DATA_DIR / "sample_expenses.json"


def print_summary(expenses):
    totals = total_by_category(expenses)
    if not totals:
        print("No expenses saved yet.")
        return
    width = max(len(name) for name in totals)
    largest = max(totals.values())
    print("Spending by category")
    print("-" * 44)
    for name, total in totals.items():
        bar = "#" * max(1, round(total / largest * 20))
        print(f"{name:<{width}}  {total:>9.2f}  {bar}")
    print("-" * 44)
    print(f"{'Total':<{width}}  {sum(totals.values()):>9.2f}")


def build_parser():
    parser = argparse.ArgumentParser(description="Track personal expenses.")
    commands = parser.add_subparsers(dest="command")
    add = commands.add_parser("add", help="record one expense")
    add.add_argument("--amount", type=float, required=True)
    add.add_argument("--category", choices=CATEGORIES, required=True)
    add.add_argument("--note", default="")
    commands.add_parser("summary", help="show totals per category")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "add":
        expenses = load_expenses(DEFAULT_PATH)
        try:
            record = add_expense(expenses, args.amount, args.category, args.note)
        except ValueError as error:
            print(f"Error: {error}")
            return 1
        save_expenses(expenses, DEFAULT_PATH)
        print(f"Saved: {record['date']}  {record['category']}  {record['amount']:.2f}  {record['note']}")
        return 0
    if args.command == "summary":
        print_summary(load_expenses(DEFAULT_PATH))
        return 0
    # No arguments: a non-interactive demo, so the program can run anywhere.
    print("Expense Tracker demo (sample data)")
    print_summary(load_expenses(Path(SAMPLE_PATH)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
