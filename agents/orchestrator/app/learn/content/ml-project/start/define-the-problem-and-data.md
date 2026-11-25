---
title: Define the problem and prepare the data
summary: Turn a vague idea ("predict student results") into a clear machine learning problem: target, features, metric, and a first look at the data.
takeaways:
- Write down what you predict, from what, and how you will judge success before touching a model
- Check the class balance and the data quality first
- Split off the test set early and leave it alone
---
## The project

A college wants to **identify students who are at risk of failing**, early enough for teachers to help. You will build a model that predicts **pass or fail** from habits and past performance.

| Question | Answer for this project |
| --- | --- |
| What do we predict? (the **target**) | `passed`: 1 if the student passed, 0 if not |
| From what? (the **features**) | attendance, study hours, previous score, sleep, assignments done, phone hours |
| Type of problem | **classification** (two classes) |
| Who uses it? | teachers, who then offer extra help |
| Which mistake is worse? | missing a student who will fail (they get no help) is worse than flagging one who would have passed, so **recall for "fail"** matters |
| Baseline to beat | always predicting the most common outcome |

## Create the practice data

Real student data is private, so we generate a realistic practice dataset (800 students). The method you learn applies unchanged to real data.

```python
import numpy as np
import pandas as pd

rng = np.random.default_rng(7)
n = 800
attendance = np.clip(rng.normal(75, 15, n), 30, 100)
study = np.clip(rng.normal(3, 1.5, n), 0, 10)
previous = np.clip(rng.normal(60, 15, n), 0, 100)
sleep = np.clip(rng.normal(7, 1.2, n), 3, 10)
assignments = np.clip(np.round(rng.normal(7, 2.5, n)), 0, 10)
phone = np.clip(rng.normal(4, 2, n), 0, 12)

raw = 0.035 * attendance + 0.40 * study + 0.045 * previous + 0.12 * assignments - 0.15 * phone + 0.10 * (sleep - 7)
chance_of_passing = 1 / (1 + np.exp(-(0.9 + 1.8 * (raw - raw.mean()))))
passed = (rng.random(n) < chance_of_passing).astype(int)        # real life is noisy: the same habits do not always give the same result

students = pd.DataFrame({
    "attendance_pct": attendance.round(1), "study_hours": study.round(1), "previous_score": previous.round(1),
    "sleep_hours": sleep.round(1), "assignments_done": assignments.astype(int), "phone_hours": phone.round(1), "passed": passed,
})
students.to_csv("students.csv", index=False)
print(students.shape)
print(students.head(3))
```

```output
(800, 7)
   attendance_pct  study_hours  previous_score  sleep_hours  assignments_done  \
0            75.0          4.0            34.6          5.6                 7
1            79.5          2.8            54.5          7.9                 8
2            70.9          3.5            59.4          6.7                10

   phone_hours  passed
0          5.5       0
1          6.1       1
2          2.0       1
```

## Look before you model

```python
df = pd.read_csv("students.csv")
print("missing values:", int(df.isna().sum().sum()))
print("duplicate rows:", int(df.duplicated().sum()))
print()
print("class balance:")
print(df["passed"].value_counts().rename({1: "passed", 0: "failed"}).to_string())
print("pass rate:", round(df["passed"].mean(), 3))
print()
print(df.groupby("passed").mean().round(1).T.rename(columns={0: "failed", 1: "passed"}).to_string())
```

```output
missing values: 0
duplicate rows: 0

class balance:
passed
passed    500
failed    300
pass rate: 0.625

passed            failed  passed
attendance_pct      68.6    76.1
study_hours          2.6     3.3
previous_score      51.9    64.3
sleep_hours          6.8     7.1
assignments_done     6.4     7.1
phone_hours          4.5     3.6
```

Read it like an analyst: no missing values, about 62% pass, and the students who passed have **higher attendance, more study hours, a better previous score and fewer phone hours** on average. The pattern is there, so a model has something to learn. The differences are averages, not rules, so the model will never be perfect.

## Correlations

```python
print(df.corr()["passed"].drop("passed").sort_values(ascending=False).round(2).to_string())
```

```output
previous_score      0.40
attendance_pct      0.26
study_hours         0.23
assignments_done    0.14
sleep_hours         0.11
phone_hours        -0.22
```

Correlation with the target is a quick first look (not proof). Be careful about **cause**: "phone hours" being linked to failing does not prove phones cause failure; it may be a sign of something else.

## Split first: protect the test set

```python
from sklearn.model_selection import train_test_split

X = df.drop(columns="passed")
y = df["passed"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=0, stratify=y)

print("train:", X_train.shape, " test:", X_test.shape)
print("pass rate in train:", round(y_train.mean(), 3), " in test:", round(y_test.mean(), 3))
```

```output
train: (600, 6)  test: (200, 6)
pass rate in train: 0.625  in test: 0.625
```

`stratify=y` keeps the pass rate the same in both parts. The **test set is locked away**: we will use it once, at the end, to judge the final model. All choices (models, settings) are made on the training data with cross-validation.

:::warning
Any decision made after looking at the test set (picking a model because it scored best there) quietly makes the final score optimistic. Keep the test set untouched until the very end.
:::

:::practice capstone-project
Ask the Capstone Project agent whether your own problem statement states the target, features, metric and baseline clearly.
:::
