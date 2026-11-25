---
title: Project 2: Expense tracker
summary: Build a tracker that records expenses, totals them by category and month, and saves and loads data from a CSV file.
takeaways:
- Model each expense as a dictionary, and keep them in a list
- Group and total with a dictionary, and format money consistently
- Save data to CSV so it survives after the program ends
---
## The idea

Many students lose track of where their money goes. Our tracker will:

1. record an expense (date, category, amount, note),
2. show the total and a breakdown by category,
3. show a monthly summary,
4. save to and load from a file.

## Step 1: the data

An expense has several facts, so a **dictionary** fits well. A list holds all expenses.

```python
expenses = []

def add_expense(expenses, date, category, amount, note=""):
    if amount <= 0:
        raise ValueError("The amount must be more than zero")
    expenses.append({"date": date, "category": category.lower(), "amount": round(float(amount), 2), "note": note})

add_expense(expenses, "2026-03-02", "Food", 120, "lunch")
add_expense(expenses, "2026-03-03", "Travel", 45.5, "bus pass")
add_expense(expenses, "2026-03-05", "Food", 80, "snacks")
add_expense(expenses, "2026-03-09", "Books", 350, "Python book")
add_expense(expenses, "2026-04-01", "Travel", 60, "metro")
add_expense(expenses, "2026-04-02", "Food", 150, "dinner")

print(len(expenses), "expenses recorded")
print(expenses[0])
```

```output
6 expenses recorded
{'date': '2026-03-02', 'category': 'food', 'amount': 120.0, 'note': 'lunch'}
```

Notice the checks inside `add_expense`: a negative or zero amount raises an error, the category is made lowercase (so "Food" and "food" are the same), and the amount is rounded to two places.

```python
try:
    add_expense(expenses, "2026-03-10", "Food", -50)
except ValueError as error:
    print("Rejected:", error)
```

```output
Rejected: The amount must be more than zero
```

## Step 2: totals and groups

```python
def total(expenses):
    return round(sum(e["amount"] for e in expenses), 2)

def by_category(expenses):
    totals = {}
    for e in expenses:
        totals[e["category"]] = totals.get(e["category"], 0) + e["amount"]
    return {category: round(value, 2) for category, value in totals.items()}

print("Total spent:", total(expenses))
for category, value in sorted(by_category(expenses).items(), key=lambda item: item[1], reverse=True):
    print(f"  {category:<8} {value:>8.2f}")
```

```output
Total spent: 805.5
  food       350.00
  books      350.00
  travel     105.50
```

`totals.get(category, 0) + amount` is the classic pattern for grouping: start at 0 for a new key, add each amount.

## Step 3: monthly summary

The first seven characters of an ISO date (`2026-03-02`) give the month (`2026-03`).

```python
def by_month(expenses):
    totals = {}
    for e in expenses:
        month = e["date"][:7]
        totals[month] = totals.get(month, 0) + e["amount"]
    return {month: round(value, 2) for month, value in sorted(totals.items())}

def biggest(expenses, n=3):
    return sorted(expenses, key=lambda e: e["amount"], reverse=True)[:n]

print(by_month(expenses))
print("Largest expenses:")
for e in biggest(expenses):
    print(f"  {e['date']}  {e['category']:<7} {e['amount']:>7.2f}  {e['note']}")
```

```output
{'2026-03': 595.5, '2026-04': 210.0}
Largest expenses:
  2026-03-09  books    350.00  Python book
  2026-04-02  food     150.00  dinner
  2026-03-02  food     120.00  lunch
```

Writing dates as `YYYY-MM-DD` has a bonus: they sort correctly as plain text.

## Step 4: show a report

```python
def report(expenses):
    lines = ["EXPENSE REPORT", "=" * 30]
    for month, value in by_month(expenses).items():
        lines.append(f"{month}: {value:>10.2f}")
    lines.append("-" * 30)
    lines.append(f"Total: {total(expenses):>10.2f}")
    top_category, top_value = max(by_category(expenses).items(), key=lambda item: item[1])
    share = 100 * top_value / total(expenses)
    lines.append(f"Biggest category: {top_category} ({share:.0f}% of spending)")
    return "\n".join(lines)

print(report(expenses))
```

```output
EXPENSE REPORT
==============================
2026-03:     595.50
2026-04:     210.00
------------------------------
Total:     805.50
Biggest category: food (43% of spending)
```

The report returns a string instead of printing, so it can be printed, written to a file, or shown on a web page.

## Step 5: save and load with CSV

Without saving, everything vanishes when the program closes. A **CSV** file stores a table as plain text and opens in Excel.

```python
import csv
import io

FIELDS = ["date", "category", "amount", "note"]

def save_csv(expenses, file):
    writer = csv.DictWriter(file, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(expenses)

def load_csv(file):
    return [
        {"date": row["date"], "category": row["category"], "amount": float(row["amount"]), "note": row["note"]}
        for row in csv.DictReader(file)
    ]

buffer = io.StringIO()                 # a pretend file in memory; use open("expenses.csv", "w", newline="") for a real one
save_csv(expenses, buffer)
print(buffer.getvalue())

buffer.seek(0)
loaded = load_csv(buffer)
print("loaded back identical:", loaded == expenses)
```

```output
date,category,amount,note
2026-03-02,food,120.0,lunch
2026-03-03,travel,45.5,bus pass
2026-03-05,food,80.0,snacks
2026-03-09,books,350.0,Python book
2026-04-01,travel,60.0,metro
2026-04-02,food,150.0,dinner

loaded back identical: True
```

With a real file the code is:

```py
with open("expenses.csv", "w", newline="", encoding="utf-8") as file:
    save_csv(expenses, file)

with open("expenses.csv", newline="", encoding="utf-8") as file:
    expenses = load_csv(file)
```

`newline=""` prevents blank lines on Windows. Notice that `load_csv` converts the amount back to a number: everything read from a CSV is **text** until you convert it.

:::warning
Handle the case where the file does not exist yet (the first run). Use `try ... except FileNotFoundError:` and start with an empty list. Always open files with a `with` block so they are closed properly.
:::

## Step 6: a simple menu (interactive)

```py
def main():
    try:
        with open("expenses.csv", newline="", encoding="utf-8") as file:
            expenses = load_csv(file)
    except FileNotFoundError:
        expenses = []

    while True:
        print("\n1) Add expense  2) Report  3) Save and quit")
        choice = input("Choose: ").strip()
        if choice == "1":
            date = input("Date (YYYY-MM-DD): ")
            category = input("Category: ")
            amount = float(input("Amount: "))
            add_expense(expenses, date, category, amount, input("Note: "))
        elif choice == "2":
            print(report(expenses))
        elif choice == "3":
            with open("expenses.csv", "w", newline="", encoding="utf-8") as file:
                save_csv(expenses, file)
            break
```

The menu is a thin layer. All the real work lives in functions we tested above.

## Improvements to try

| Idea | What you practise |
| --- | --- |
| validate the date with `datetime.strptime` | dates, error handling |
| monthly budgets and a warning when you exceed them | dictionaries, conditions |
| delete or edit an expense | lists and indexes |
| a bar chart per category with `matplotlib` | libraries, data visualisation |
| export to Excel with `pandas` or `openpyxl` | libraries |
| a web version with Flask | the next course in this section |

:::practice capstone-project
Ask the Capstone Project agent to suggest three extra features for your tracker and the order in which to build them.
:::
