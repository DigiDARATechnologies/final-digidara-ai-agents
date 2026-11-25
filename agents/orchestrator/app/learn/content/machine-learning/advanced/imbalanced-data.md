---
title: Imbalanced data
summary: Handle problems where one class is rare, such as fraud or disease: why accuracy lies, and how class weights, better metrics and thresholds fix it.
takeaways:
- With rare classes, accuracy is misleading; a model that always says "no" can score 95%
- Use precision, recall, F1 and the precision-recall curve
- Fix it with class weights, resampling, and by moving the decision threshold
---
## Rare events are common

Fraud, equipment failure, a disease, a customer who will cancel: the thing you care about usually happens **rarely**. If 5 of every 100 transactions are fraud, a lazy model that answers "not fraud" every time is **95% accurate** and completely useless.

```python
import numpy as np
from sklearn.datasets import make_classification
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, recall_score

X, y = make_classification(n_samples=4000, n_features=10, n_informative=5, n_redundant=0, weights=[0.95, 0.05],
                           flip_y=0.01, class_sep=1.5, random_state=0)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, stratify=y, random_state=0)

print("share of the rare class:", round(float(y.mean()), 3))

lazy = DummyClassifier(strategy="most_frequent").fit(X_train, y_train)
pred = lazy.predict(X_test)
print("lazy model accuracy:", round(accuracy_score(y_test, pred), 3))
print("lazy model recall  :", round(recall_score(y_test, pred), 3))
```

```output
share of the rare class: 0.055
lazy model accuracy: 0.945
lazy model recall  : 0.0
```

The always-"no" model is about 95% accurate but catches **none** of the rare cases (recall 0). Accuracy hides the failure.

Always use `stratify=y` in the split so the rare class appears in both train and test in the same proportion.

## Better metrics

| Metric | Question it answers |
| --- | --- |
| **Recall** (sensitivity) | of all the real positives, how many did we catch? |
| **Precision** | of everything we flagged, how many were truly positive? |
| **F1** | a balance of precision and recall |
| **PR-AUC** (average precision) | quality across all thresholds, honest for rare classes |
| **ROC-AUC** | ranking quality; can look flattering when positives are rare |
| **Confusion matrix** | the four counts behind everything |

Which matters more depends on the cost of mistakes. Missing a cancer case is far worse than a false alarm, so aim for high recall. Blocking a good customer's card is costly too, so fraud teams balance the two.

## A model that actually looks for the rare class

```python
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, f1_score, average_precision_score

def report(name, model):
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]
    print(f"{name:<22} precision {precision_score(y_test, pred, zero_division=0):.2f}  recall {recall_score(y_test, pred):.2f}  "
          f"F1 {f1_score(y_test, pred):.2f}  PR-AUC {average_precision_score(y_test, proba):.2f}")

report("plain", make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)))
report("class_weight='balanced'", make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced")))
```

```output
plain                  precision 0.94  recall 0.74  F1 0.83  PR-AUC 0.86
class_weight='balanced' precision 0.48  recall 0.89  F1 0.62  PR-AUC 0.86
```

`class_weight="balanced"` makes mistakes on the rare class count more during training. The result: **recall rises** (from 0.74 to 0.89) but **precision drops** (from 0.94 to 0.48), because the model now flags many more cases. Notice that the PR-AUC is the same for both: the model ranks cases about equally well, and class weights simply moved the **operating point**. Whether that trade is good is a business decision.

## Move the threshold

A classifier gives a **probability**, and `predict` simply cuts it at 0.5. For rare events, 0.5 is rarely the right cut. Choose it using the precision-recall trade-off:

```python
model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(X_train, y_train)
proba = model.predict_proba(X_test)[:, 1]

print("threshold  precision  recall")
for threshold in (0.5, 0.3, 0.2, 0.1, 0.05):
    pred = (proba >= threshold).astype(int)
    print(f"{threshold:>9}  {precision_score(y_test, pred, zero_division=0):>9.2f}  {recall_score(y_test, pred):>6.2f}")
```

```output
threshold  precision  recall
      0.5       0.94    0.74
      0.3       0.88    0.79
      0.2       0.80    0.80
      0.1       0.57    0.85
     0.05       0.38    0.91
```

Lowering the threshold catches more of the rare class (recall goes up) while precision falls. Pick the point that fits the cost of each kind of mistake, using a **validation set**, not the test set.

## Resampling

| Technique | What it does | Caution |
| --- | --- | --- |
| **random oversampling** | duplicates rare-class rows | can overfit those exact rows |
| **random undersampling** | drops common-class rows | throws away information |
| **SMOTE** (`imbalanced-learn`) | creates new, synthetic rare-class rows between neighbours | only in the **training** data, inside the pipeline |
| **class weights** | reweights the loss, no data change | the simplest, try this first |

```py
pip install imbalanced-learn
from imblearn.pipeline import Pipeline
from imblearn.over_sampling import SMOTE

pipe = Pipeline([("smote", SMOTE(random_state=0)), ("model", LogisticRegression(max_iter=1000))])
```

:::warning
Never resample **before** splitting, and never resample the test set. Do it only inside the training folds (an `imblearn` pipeline does this), or copies of the same row end up in both train and test and the score becomes meaningless.
:::

## Other helpful approaches

| Approach | Use |
| --- | --- |
| **anomaly detection** (Isolation Forest) | when the rare class is very rare and varied |
| **cost-sensitive learning** | give each mistake a real cost and minimise total cost |
| **ensembles of balanced samples** | `BalancedRandomForestClassifier` |
| **collect more rare examples** | often the best investment |

:::interview
**Interviewers often ask:** "How do you handle an imbalanced dataset?" Use stratified splits and metrics such as precision, recall, F1 and PR-AUC rather than accuracy. Try class weights, then resampling such as SMOTE (only on training data), and tune the decision threshold for the cost trade-off. Consider anomaly detection or collecting more positive examples.
:::
