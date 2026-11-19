---
title: Testing, error handling and polishing your project
summary: Make a project reliable and professional with automated tests, good error handling, clean structure and a README.
takeaways:
- Automated tests check your code in seconds and catch mistakes when you change things
- Test normal cases, boundaries and invalid input
- A tidy structure, helpful error messages and a README turn a script into a project
---
## Why test

Imagine adding a feature to your marks manager and accidentally breaking the grade calculation. Without tests, you may not notice until a student gets the wrong grade. With tests, a command tells you in two seconds.

## The grade function and its tests

A small function to test:

```python
def grade(average):
    if not 0 <= average <= 100:
        raise ValueError("Average must be between 0 and 100")
    if average >= 90:
        return "A"
    if average >= 75:
        return "B"
    if average >= 50:
        return "C"
    return "F"
```

Think of the **boundaries**, where bugs hide: the values just below and just on each limit.

```python
import unittest

class GradeTests(unittest.TestCase):
    def test_normal_values(self):
        self.assertEqual(grade(95), "A")
        self.assertEqual(grade(80), "B")
        self.assertEqual(grade(60), "C")
        self.assertEqual(grade(20), "F")

    def test_boundaries(self):
        self.assertEqual(grade(90), "A")          # exactly on the limit
        self.assertEqual(grade(89.99), "B")       # just below it
        self.assertEqual(grade(75), "B")
        self.assertEqual(grade(74.99), "C")
        self.assertEqual(grade(50), "C")
        self.assertEqual(grade(49.99), "F")

    def test_extremes(self):
        self.assertEqual(grade(0), "F")
        self.assertEqual(grade(100), "A")

    def test_invalid_input_is_rejected(self):
        with self.assertRaises(ValueError):
            grade(101)
        with self.assertRaises(ValueError):
            grade(-1)

import io
suite = unittest.defaultTestLoader.loadTestsFromTestCase(GradeTests)
result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
print("tests run:", result.testsRun, "| failures:", len(result.failures), "| errors:", len(result.errors), "| all passed:", result.wasSuccessful())
```

```output
tests run: 4 | failures: 0 | errors: 0 | all passed: True
```

All four tests pass. In a real project, save the tests in `tests/test_grades.py` and run them from the terminal:

```py
python -m unittest          # built in, no installation needed
pip install pytest
pytest                      # shorter test style and nicer output
```

With pytest the same tests are plain functions:

```py
import pytest

def test_boundaries():
    assert grade(90) == "A"
    assert grade(89.99) == "B"

def test_invalid_input():
    with pytest.raises(ValueError):
        grade(101)
```

## What a test should do

| Rule | Why |
| --- | --- |
| **test one behaviour per test** | when it fails, you know exactly what broke |
| **name tests clearly** (`test_boundaries`) | the name explains the failure |
| **test the unusual**: empty lists, zero, negative numbers, huge values, wrong types | bugs live at the edges |
| **no real files, networks or keyboard input** in unit tests | use sample data; keep tests fast and repeatable |
| **run all tests before every commit** | you keep a working project |

## Error handling that helps the user

A crash message such as `KeyError: 'Maths'` helps nobody. Catch problems where you can say something useful:

```python
def safe_average(marks_text):
    try:
        marks = [float(part) for part in marks_text.split(",")]
    except ValueError:
        return None, "Please enter marks as numbers separated by commas, such as 80, 75, 92."
    if not marks:
        return None, "Please enter at least one mark."
    if any(m < 0 or m > 100 for m in marks):
        return None, "Marks must be between 0 and 100."
    return sum(marks) / len(marks), ""

for text in ("80, 75, 92", "80, abc", "80, 150", ""):
    value, message = safe_average(text)
    print(f"{text!r:<14} -> {value if value is not None else message}")
```

```output
'80, 75, 92'   -> 82.33333333333333
'80, abc'      -> Please enter marks as numbers separated by commas, such as 80, 75, 92.
'80, 150'      -> Marks must be between 0 and 100.
''             -> Please enter marks as numbers separated by commas, such as 80, 75, 92.
```

Each bad input gets a clear, specific message. The function returns a pair (value and message) so that the interface can show the message however it likes.

| Habit | Detail |
| --- | --- |
| **validate input early** | check at the edge, before the data travels deep into your code |
| **catch specific errors** (`ValueError`, `FileNotFoundError`) | not a bare `except:` that hides every bug |
| **write messages for people**: what happened and what to do | not a technical code |
| **log technical detail** for yourself | `import logging` instead of `print` in bigger projects |
| **never expose passwords, keys or internal paths** in messages | security |

## Clean code habits

| Habit | Example |
| --- | --- |
| **clear names** | `total_spent`, `is_valid`, not `t`, `flag` |
| **small functions** that do one thing | if you need "and" to describe it, split it |
| **no repeated code** | the same lines twice become a function |
| **constants in one place** | `PASS_MARK = 50` at the top, not `50` scattered through the code |
| **comments explain why**, not what | `# marks above 100 come from a data-entry error` |
| **docstrings** for functions | a short description right under `def` |
| **consistent style** | run `black` or `ruff format`, and `ruff` or `flake8` to find problems |

```python
def pass_rate(marks, pass_mark=50):
    """Return the percentage of marks that are at or above the pass mark."""
    if not marks:
        return 0.0
    return 100 * sum(m >= pass_mark for m in marks) / len(marks)

print(pass_rate([92, 48, 85, 71, 64, 55]))
print(pass_rate([]))
help_text = pass_rate.__doc__
print(help_text)
```

```output
83.33333333333333
0.0
Return the percentage of marks that are at or above the pass mark.
```

## A project README

The README is the first thing anyone sees on GitHub. A good one makes your project look professional. A simple template:

```py
# Expense Tracker

A command-line tool that records daily expenses, shows totals by category and month,
and saves your data to a CSV file.

## Features
- Add an expense with date, category, amount and note
- Monthly and category summaries
- Saves and loads from `expenses.csv`

## How to run
    python -m venv .venv
    .venv\Scripts\activate        # macOS and Linux: source .venv/bin/activate
    pip install -r requirements.txt
    python main.py

## Example
    1) Add expense  2) Report  3) Save and quit

## Tests
    python -m unittest

## What I learned
Separating the logic from the input and output made the code easy to test.
I also learned how to read and write CSV files.

## Future ideas
- Monthly budgets and warnings
- A Flask web interface
```

The Portfolio course goes deeper into READMEs, GitHub and presenting your work.

## A checklist before you call a project done

| Question | |
| --- | --- |
| Does the main feature work for normal input? | |
| Does it handle empty, wrong and extreme input without crashing? | |
| Are there tests, and do they pass? | |
| Is the code tidy: names, functions, no leftover test prints? | |
| Is there a README with how to run it? | |
| Are secrets (keys, passwords) kept out of the code? | |
| Is it on GitHub with a clear commit history? | |
| Can I explain every part and every decision in an interview? | |

:::tip
The last question matters most. Interviewers will ask "Why did you do it this way?" and "What would you change?" Make notes on your design choices and mistakes while you build: they become your best interview stories.
:::

:::practice capstone-project
Share your project and README with the Capstone Project agent and ask for a review against the checklist above.
:::
