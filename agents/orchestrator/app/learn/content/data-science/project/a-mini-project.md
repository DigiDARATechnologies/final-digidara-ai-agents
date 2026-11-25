---
title: A mini project from start to finish
summary: Walk through a complete small project: ask a question, explore, prepare, model, evaluate and report.
takeaways:
- A project follows ask, explore, prepare, model, evaluate, report
- Compare your model with a simple baseline
- Finish with a clear conclusion and its limits
---
## The question

**Can we tell which of three grape varieties a wine comes from using only its chemical measurements?** This is a **classification** problem with 178 rows and 13 numeric features.

## 1. Load and explore

```python
import pandas as pd
from sklearn.datasets import load_wine

data = load_wine(as_frame=True)
X, y = data.data, data.target
print(X.shape, y.value_counts().sort_index().tolist())
print("missing values:", int(X.isna().sum().sum()))
```

```output
(178, 13) [59, 71, 48]
missing values: 0
```

There are no missing values, and the three classes are reasonably balanced.

```python
print(X.corrwith(y).sort_values(key=abs, ascending=False).head(4).round(2))
```

```output
flavanoids                     -0.85
od280/od315_of_diluted_wines   -0.79
total_phenols                  -0.72
proline                        -0.63
dtype: float64
```

These columns are the most related to the wine type, so they are good candidates to matter in the model.

## 2. Split the data

```python
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
print(len(X_train), len(X_test))
```

```output
133 45
```

## 3. A baseline first

Before a clever model, check a naive one. If your model cannot beat it, it is not adding value.

```python
from sklearn.dummy import DummyClassifier

baseline = DummyClassifier(strategy="most_frequent").fit(X_train, y_train)
print("baseline accuracy:", round(baseline.score(X_test, y_test), 3))
```

```output
baseline accuracy: 0.4
```

Always guessing the most common class gets about 40%.

## 4. Train a model

```python
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
model.fit(X_train, y_train)
print("train accuracy:", round(model.score(X_train, y_train), 3))
print("test accuracy :", round(model.score(X_test, y_test), 3))
```

```output
train accuracy: 1.0
test accuracy : 1.0
```

## 5. Evaluate honestly

```python
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import cross_val_score

pred = model.predict(X_test)
print(confusion_matrix(y_test, pred))
print(classification_report(y_test, pred, digits=2))
scores = cross_val_score(model, X, y, cv=5)
print("5-fold CV:", scores.round(3), "mean", round(scores.mean(), 3))
```

```output
[[15  0  0]
 [ 0 18  0]
 [ 0  0 12]]
              precision    recall  f1-score   support

           0       1.00      1.00      1.00        15
           1       1.00      1.00      1.00        18
           2       1.00      1.00      1.00        12

    accuracy                           1.00        45
   macro avg       1.00      1.00      1.00        45
weighted avg       1.00      1.00      1.00        45

5-fold CV: [0.972 0.972 1.    0.971 1.   ] mean 0.983
```

## 6. What did the model learn?

```python
coefficients = pd.DataFrame(model[-1].coef_.T, index=X.columns, columns=["class_0", "class_1", "class_2"])
print(coefficients.abs().max(axis=1).sort_values(ascending=False).head(4).round(2))
```

```output
color_intensity    1.02
proline            0.94
flavanoids         0.89
alcohol            0.84
dtype: float64
```

These features pull the hardest on the prediction (the features were scaled first, so the sizes are comparable).

A perfect score on only 45 test wines is partly luck. The cross-validated 98% is the more honest number to report, because it averages five different splits.

## 7. The report

| Part | Write |
| --- | --- |
| **Question** | Can wine variety be predicted from 13 chemical measurements? |
| **Data** | 178 wines, 3 varieties, no missing values |
| **Method** | scaled features, logistic regression, 25% test set, 5-fold cross-validation |
| **Result** | 100% on the 45-wine test set, and about 98% in 5-fold cross-validation, against a baseline of about 40% |
| **Limits** | a small dataset from one source; the model has not been tried on wines from other regions |
| **Next steps** | test on new data; try a random forest; check the few mistakes |

:::remember
The model is only the middle of the project. The question, the clean data and the clear explanation matter just as much.
:::

:::practice leetcode
Build confidence in the Python behind this project by practising in Coding Practice.
:::
