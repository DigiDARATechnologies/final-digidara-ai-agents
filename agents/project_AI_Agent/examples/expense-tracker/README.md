# Expense Tracker

A small command-line program that records personal expenses, saves them to a
JSON file and shows spending per category.

> **This is an example submission.** It shows the folder structure and the
> level of detail the Capstone agent expects. Build your own project for your
> own topic; do not copy this one.

## Run it

```
pip install -r requirements.txt
python src/main.py                                   # demo on sample data
python src/main.py add --amount 250 --category Food --note "Lunch"
python src/main.py summary
python -m pytest                                     # run the tests
```

## Folder structure

```
expense-tracker/
├── README.md
├── requirements.txt
├── .gitignore
├── src/                    all source code
│   ├── main.py             command-line entry point
│   ├── tracker.py          validation and summaries
│   └── storage.py          JSON file persistence
├── tests/
│   └── test_tracker.py
├── data/
│   └── sample_expenses.json
└── output_screenshots/     proof that it runs - image files, kept in the zip (not in the .docx report)
    ├── 01-add-expense.png
    ├── 02-category-summary.png
    └── 03-tests-passing.png
```

## Features

- Add an expense with an amount, a category and a note.
- Rejects zero/negative amounts and unknown categories.
- Saves to `data/expenses.json` and reloads it on the next run.
- Prints a per-category summary with a simple text bar chart.
