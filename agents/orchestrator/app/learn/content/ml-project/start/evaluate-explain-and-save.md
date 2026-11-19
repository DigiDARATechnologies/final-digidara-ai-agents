---
title: Evaluate honestly, explain and save the model
summary: Test the final model once, read the confusion matrix, choose a threshold for the real-world cost, see which factors matter, and save it for use.
takeaways:
- Accuracy alone hides the types of error; use the confusion matrix, precision and recall
- Pick the decision threshold using the cost of each mistake
- Save the whole pipeline together with a prediction function that checks its input
---
## One honest test

```python
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_score, recall_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

df = pd.read_csv("students.csv")
X, y = df.drop(columns="passed"), df["passed"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=0, stratify=y)

model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(X_train, y_train)
predictions = model.predict(X_test)

print("test accuracy:", round(accuracy_score(y_test, predictions), 3))
print("baseline (always 'pass'):", round(y_test.mean(), 3))
```

```output
test accuracy: 0.79
baseline (always 'pass'): 0.625
```

The test accuracy is in the same range as the cross-validation estimate, which is reassuring: no sign of overfitting or leakage. And it clearly beats the baseline.

## The confusion matrix: what kinds of mistakes?

```python
tn, fp, fn, tp = confusion_matrix(y_test, predictions).ravel()
print("                 predicted FAIL   predicted PASS")
print(f"actually FAIL    {tn:>10}  (correct)   {fp:>5}  (missed at-risk student)")
print(f"actually PASS    {fn:>10}  (needless flag)  {tp:>3}  (correct)")
```

```output
                 predicted FAIL   predicted PASS
actually FAIL            49  (correct)      26  (missed at-risk student)
actually PASS            16  (needless flag)  109  (correct)
```

Here "positive" is **pass**. The most worrying cell is the top right: **students who actually failed but were predicted to pass**. Those students would get no help.

## Measure what matters: finding students who will fail

Our goal is to catch students at risk, so measure the **fail** class:

```python
at_risk_true = 1 - y_test
at_risk_score = 1 - model.predict_proba(X_test)[:, 1]            # the model's probability of failing

def risk_report(threshold):
    flagged = (at_risk_score >= threshold).astype(int)
    caught = recall_score(at_risk_true, flagged)
    correct = precision_score(at_risk_true, flagged, zero_division=0)
    return flagged.sum(), caught, correct

print("threshold  students flagged  share of failing students caught  share of flagged who truly fail")
for threshold in (0.5, 0.4, 0.3, 0.2):
    flagged, caught, correct = risk_report(threshold)
    print(f"{threshold:>9}  {flagged:>16}  {caught:>31.2f}  {correct:>30.2f}")
```

```output
threshold  students flagged  share of failing students caught  share of flagged who truly fail
      0.5                65                             0.65                            0.75
      0.4                87                             0.81                            0.70
      0.3               107                             0.91                            0.64
      0.2               126                             0.96                            0.57
```

This is the trade-off in plain numbers. With the usual 0.5 cut, the model catches 65% of the students who will fail and misses the other 35%. If you **lower** the threshold, the model flags more students and **catches more** of the real failures, but more flagged students turn out to be fine. A college would pick the point where the teachers can handle the number of flagged students. **The threshold is a business decision**, not a technical one.

## What does the model look at?

```python
coefficients = pd.Series(model.named_steps["logisticregression"].coef_[0], index=X.columns).sort_values(ascending=False)
print(coefficients.round(2).to_string())
```

```output
previous_score      1.27
attendance_pct      0.77
study_hours         0.77
assignments_done    0.40
sleep_hours         0.21
phone_hours        -0.56
```

Because the inputs were scaled, the sizes are comparable: positive numbers push towards **pass**, negative towards **fail**. This is a big advantage of logistic regression: you can **explain** it to teachers ("previous score matters most, then attendance and study hours; phone hours pull the chance of passing down").

```python
from sklearn.inspection import permutation_importance

result = permutation_importance(model, X_test, y_test, n_repeats=20, random_state=0)
for name, drop in sorted(zip(X.columns, result.importances_mean), key=lambda item: -item[1]):
    print(f"{name:<18} accuracy drops by {drop:.3f} when shuffled")
```

```output
previous_score     accuracy drops by 0.120 when shuffled
attendance_pct     accuracy drops by 0.056 when shuffled
study_hours        accuracy drops by 0.047 when shuffled
phone_hours        accuracy drops by 0.032 when shuffled
assignments_done   accuracy drops by 0.018 when shuffled
sleep_hours        accuracy drops by -0.001 when shuffled
```

Permutation importance agrees: shuffling the important columns hurts accuracy; shuffling a useless one does nothing.

## Save the model

Save the **whole pipeline** (scaler and model together) so that predictions use the same scaling as training:

```python
import joblib

joblib.dump(model, "student_model.joblib")
loaded = joblib.load("student_model.joblib")
print("loaded model gives the same predictions:", bool((loaded.predict(X_test) == predictions).all()))
```

```output
loaded model gives the same predictions: True
```

## A safe prediction function

Wrap the model so that wrong input produces a clear error, not a silent wrong answer:

```python
LIMITS = {
    "attendance_pct": (0, 100), "study_hours": (0, 16), "previous_score": (0, 100),
    "sleep_hours": (0, 16), "assignments_done": (0, 10), "phone_hours": (0, 16),
}

def predict_student(model, record):
    missing = [name for name in LIMITS if name not in record]
    if missing:
        raise ValueError(f"Missing fields: {missing}")
    for name, (low, high) in LIMITS.items():
        if not low <= record[name] <= high:
            raise ValueError(f"{name} must be between {low} and {high}")
    row = pd.DataFrame([record])[list(LIMITS)]
    chance_of_passing = float(model.predict_proba(row)[0, 1])
    return {"chance_of_passing": round(chance_of_passing, 2), "at_risk": chance_of_passing < 0.6}

strong = {"attendance_pct": 92, "study_hours": 4.5, "previous_score": 78, "sleep_hours": 7.5, "assignments_done": 9, "phone_hours": 2}
weak = {"attendance_pct": 55, "study_hours": 1, "previous_score": 40, "sleep_hours": 5, "assignments_done": 3, "phone_hours": 7}
print("strong habits:", predict_student(loaded, strong))
print("weak habits  :", predict_student(loaded, weak))

try:
    predict_student(loaded, {**strong, "attendance_pct": 250})
except ValueError as error:
    print("bad input rejected:", error)
```

```output
strong habits: {'chance_of_passing': 0.99, 'at_risk': False}
weak habits  : {'chance_of_passing': 0.01, 'at_risk': True}
bad input rejected: attendance_pct must be between 0 and 100
```

The model gives sensible answers: a high chance of passing for the strong profile and a low one for the weak profile, and impossible input is refused.
