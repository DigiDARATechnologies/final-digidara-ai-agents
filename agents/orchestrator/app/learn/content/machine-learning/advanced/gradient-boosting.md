---
title: Gradient boosting
summary: Learn how boosting builds a strong model from many weak trees, then use scikit-learn's HistGradientBoosting and understand XGBoost and LightGBM.
takeaways:
- Boosting adds small trees one after another, each fixing the mistakes of the ones before
- Learning rate, number of trees and tree depth work together; early stopping picks the number of trees
- Gradient boosting is usually the strongest method for tabular data
---
## Bagging versus boosting

Both combine many decision trees, but in opposite ways:

| | Random forest (bagging) | Gradient boosting |
| --- | --- | --- |
| How trees are built | **independently**, in parallel, on random samples | **one after another**, each learning from the previous |
| Each tree is | deep and complex | small and simple ("weak") |
| Combined by | averaging (votes) | adding up small corrections |
| Reduces mainly | variance | bias (and with care, variance) |
| Risk | rarely overfits badly | can overfit if you add too many trees |

## The idea by hand

Start with a very simple prediction (the average). Look at the **mistakes** (residuals). Train a small tree to predict those mistakes. Add a **fraction** of its predictions to the model. Repeat. Each round, the leftover mistakes shrink.

```python
import numpy as np
from sklearn.datasets import load_diabetes
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeRegressor
from sklearn.metrics import mean_squared_error

X, y = load_diabetes(return_X_y=True)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=0)

learning_rate = 0.1
prediction_train = np.full(len(y_train), y_train.mean())      # round 0: just the average
prediction_test = np.full(len(y_test), y_train.mean())

print("round  train RMSE  test RMSE")
for round_number in range(0, 101):
    if round_number in (0, 1, 5, 20, 50, 100):
        train_rmse = mean_squared_error(y_train, prediction_train) ** 0.5
        test_rmse = mean_squared_error(y_test, prediction_test) ** 0.5
        print(f"{round_number:>5}  {train_rmse:>10.1f}  {test_rmse:>9.1f}")
    residuals = y_train - prediction_train                     # the current mistakes
    tree = DecisionTreeRegressor(max_depth=2, random_state=0).fit(X_train, residuals)
    prediction_train += learning_rate * tree.predict(X_train)  # add a small correction
    prediction_test += learning_rate * tree.predict(X_test)
```

```output
round  train RMSE  test RMSE
    0        79.3       71.4
    1        75.5       68.5
    5        65.1       61.5
   20        50.8       56.8
   50        44.2       57.0
  100        39.2       58.1
```

Training error falls with every round, because each small tree fixes some of what is left. Test error falls too, at first, which is the point of boosting. But after about 20 rounds it stops improving and creeps back up (56.8, then 57.0, then 58.1) while training error keeps falling: the model has started to memorise noise. This is why boosting needs **early stopping** (below). You wrote the whole algorithm in a dozen lines: that loop **is** gradient boosting for squared error (the "gradient" is the residual).

## Using scikit-learn

`HistGradientBoostingClassifier` and `HistGradientBoostingRegressor` are fast, handle missing values on their own, and need no scaling:

```python
from sklearn.datasets import load_breast_cancer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import cross_val_score

data = load_breast_cancer()
models = {
    "random forest": RandomForestClassifier(n_estimators=200, random_state=0),
    "gradient boosting": HistGradientBoostingClassifier(random_state=0),
}
for name, model in models.items():
    scores = cross_val_score(model, data.data, data.target, cv=5)
    print(f"{name:<18} {scores.mean():.3f}")
```

```output
random forest      0.960
gradient boosting  0.967
```

On this small, easy dataset the two are close. On larger tabular data with many feature interactions, boosting usually pulls ahead.

## The important settings

| Setting | Meaning | Guidance |
| --- | --- | --- |
| `learning_rate` | how much of each tree to add | small (0.03 to 0.1) is safer but needs more trees |
| `max_iter` (number of trees) | how many rounds | pair with early stopping |
| `max_depth` / `max_leaf_nodes` | size of each tree | keep trees small (3 to 8 levels) |
| `min_samples_leaf` | smallest leaf | larger values reduce overfitting |
| `l2_regularization` | penalty on leaf values | helps on noisy data |
| `early_stopping` | stop when the validation score stops improving | saves time and prevents overfitting |

A smaller learning rate with more trees usually gives a better model, at the cost of training time.

## Early stopping

Let the model decide how many trees it needs:

```python
model = HistGradientBoostingClassifier(
    max_iter=1000, learning_rate=0.1, early_stopping=True,
    validation_fraction=0.2, n_iter_no_change=10, random_state=0,
)
model.fit(data.data, data.target)
print("trees asked for: 1000   trees actually built:", model.n_iter_)
```

```output
trees asked for: 1000   trees actually built: 101
```

It set aside 20% of the training data, watched the score on it, and stopped once 10 rounds in a row brought no improvement. Far fewer than 1,000 trees were needed.

## XGBoost, LightGBM and CatBoost

These are specialised libraries for the same idea, with more speed and options. They dominate competitions on tabular data.

| Library | Known for |
| --- | --- |
| **XGBoost** | the classic; very robust and widely used |
| **LightGBM** | very fast on large data; leaf-wise tree growth |
| **CatBoost** | handles categorical columns directly with little tuning |

They all follow the scikit-learn style:

```py
pip install xgboost lightgbm catboost

from xgboost import XGBClassifier
model = XGBClassifier(n_estimators=500, learning_rate=0.05, max_depth=4, subsample=0.8, colsample_bytree=0.8)
model.fit(X_train, y_train, eval_set=[(X_val, y_val)], early_stopping_rounds=30)
```

`subsample` and `colsample_bytree` use random parts of the rows and columns for each tree, which adds regularisation.

## When boosting is the right tool

| Choose gradient boosting for | Prefer something else for |
| --- | --- |
| tables of numbers and categories | images, audio, raw text (use deep learning) |
| a strong first model with little preprocessing | very tiny datasets (a simple model may do better) |
| competitions and business prediction | when you need a model a customer can read in one glance (a small tree or linear model) |

:::warning
Tuning on the **test set** is the usual mistake. Tune with cross-validation on training data, and touch the test set **once**, at the very end.
:::

:::interview
**Interviewers often ask:** "Random forest versus gradient boosting?" A random forest builds deep trees independently on random samples and averages them, which lowers variance. Gradient boosting builds shallow trees sequentially, each trained on the errors of the current ensemble, which lowers bias, usually reaching higher accuracy but needing more careful tuning and early stopping to avoid overfitting.
:::
