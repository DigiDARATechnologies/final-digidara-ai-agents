---
title: Baseline, model comparison and tuning
summary: Beat a simple baseline, compare several models fairly with cross-validation, tune the best one, and pick it without peeking at the test set.
takeaways:
- Always compare with a baseline so you know the model adds value
- Compare models with cross-validation on the training data only
- A simple model that is nearly as good as a complex one is usually the better choice
---
## Start with a baseline

A baseline is the dumbest sensible model. If your model cannot beat it, it is not useful.

```python
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import train_test_split, cross_val_score

df = pd.read_csv("students.csv")
X, y = df.drop(columns="passed"), df["passed"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=0, stratify=y)

baseline = DummyClassifier(strategy="most_frequent")
scores = cross_val_score(baseline, X_train, y_train, cv=5)
print("baseline (always predict 'pass') accuracy:", round(scores.mean(), 3))
```

```output
baseline (always predict 'pass') accuracy: 0.625
```

Just saying "everyone passes" is right about 62% of the time. **Any model must beat this number** to be worth using.

## A first real model

```python
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

logistic = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
scores = cross_val_score(logistic, X_train, y_train, cv=5)
print("logistic regression, 5 folds:", np.round(scores, 3))
print("mean accuracy:", round(scores.mean(), 3))
```

```output
logistic regression, 5 folds: [0.783 0.8   0.833 0.733 0.767]
mean accuracy: 0.783
```

The scaler is **inside the pipeline**, so each fold fits it only on its own training part. That avoids data leakage.

## Compare several models fairly

```python
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.tree import DecisionTreeClassifier

candidates = {
    "baseline": DummyClassifier(strategy="most_frequent"),
    "logistic regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
    "decision tree (depth 4)": DecisionTreeClassifier(max_depth=4, random_state=0),
    "random forest": RandomForestClassifier(n_estimators=200, random_state=0),
    "gradient boosting": HistGradientBoostingClassifier(random_state=0),
}
for name, model in candidates.items():
    cv_scores = cross_val_score(model, X_train, y_train, cv=5)
    print(f"{name:<25} {cv_scores.mean():.3f}  (+/- {cv_scores.std():.3f})")
```

```output
baseline                  0.625  (+/- 0.000)
logistic regression       0.783  (+/- 0.033)
decision tree (depth 4)   0.715  (+/- 0.014)
random forest             0.743  (+/- 0.028)
gradient boosting         0.765  (+/- 0.031)
```

Every model beats the baseline. The three strongest (logistic regression, gradient boosting and the random forest) are within about four points of each other, which is roughly the size of the +/- spread between folds, and the single tree is clearly behind. When complex models do not clearly win, choose the **simplest** one: it is easier to explain to teachers, faster, and less likely to overfit. Here that is logistic regression. This is a common real-world result on small tables with noisy outcomes.

## Tune the chosen model

A small search over the regularisation strength `C` (a smaller `C` means a stronger penalty):

```python
from sklearn.model_selection import GridSearchCV

search = GridSearchCV(
    make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
    param_grid={"logisticregression__C": [0.01, 0.1, 1, 10]},
    cv=5,
)
search.fit(X_train, y_train)

print("best C:", search.best_params_["logisticregression__C"])
print("best cross-validated accuracy:", round(search.best_score_, 3))
for c, score in zip(search.cv_results_["param_logisticregression__C"], search.cv_results_["mean_test_score"]):
    print(f"  C = {c:<5} -> {score:.3f}")
```

```output
best C: 10
best cross-validated accuracy: 0.785
  C = 0.01  -> 0.757
  C = 0.1   -> 0.778
  C = 1.0   -> 0.783
  C = 10.0  -> 0.785
```

Apart from the strongest penalty (`C = 0.01`), which costs about three points, the scores barely change across `C` (0.778 to 0.785), so the model is **not sensitive** to this setting. Do not spend hours tuning a setting that does not matter; time is better spent on better data or features.

## Try a better feature

Domain knowledge can help more than tuning. Perhaps students who study **and** attend do especially well:

```python
def add_features(frame):
    frame = frame.copy()
    frame["effort"] = frame["study_hours"] * frame["attendance_pct"] / 100
    frame["screen_ratio"] = frame["phone_hours"] / (frame["study_hours"] + 1)
    return frame

with_features = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
plain = cross_val_score(with_features, X_train, y_train, cv=5).mean()
engineered = cross_val_score(with_features, add_features(X_train), y_train, cv=5).mean()
print("original features :", round(plain, 3))
print("with 2 new features:", round(engineered, 3))
```

```output
original features : 0.783
with 2 new features: 0.788
```

Keep a new feature **only if the cross-validated score improves** by more than the noise. Here the gain is half a point (0.783 to 0.788), well inside the fold-to-fold spread of about three points, so we **drop** the new features: simpler is better. Never judge a feature on the test set.

## Decision

| Choice | Reason |
| --- | --- |
| model | logistic regression with scaling |
| why | as accurate as the complex models here, easy to explain, fast, stable |
| settings | the default `C = 1` (tuning made no real difference) |

We will now measure it **once** on the test set.
