---
title: Anomaly detection
summary: Find the unusual points that do not fit the pattern, with a simple z-score rule and with Isolation Forest, and know how to judge the alerts.
takeaways:
- An anomaly is a point that is rare and different from the rest: fraud, a faulty sensor, an attack
- Simple statistics work for one number; Isolation Forest handles many
- Alerts are only candidates: measure precision and let a person review them
---
## What is an anomaly

An **anomaly** (outlier) is an observation that does not fit the normal pattern: a card payment far from your usual spending, an engine temperature that jumps, a login from a strange country.

The difficulty is that anomalies are **rare**, and you often have **no labels** saying which points are bad. So the approach is to learn what **normal** looks like and flag what is far from it.

## A practice dataset

```python
import numpy as np

rng = np.random.default_rng(0)
normal = rng.normal(loc=[50, 50], scale=[8, 8], size=(500, 2))                 # 500 ordinary points
planted = np.array([[95, 20], [10, 85], [100, 100], [5, 5], [90, 95], [15, 15], [98, 10], [8, 92]], dtype=float)   # 8 planted oddities
data = np.vstack([normal, planted])
is_anomaly = np.array([0] * len(normal) + [1] * len(planted))

print("points:", len(data), "| planted anomalies:", int(is_anomaly.sum()))
```

```output
points: 508 | planted anomalies: 8
```

## Method 1: the z-score rule (one number)

From the Statistics lesson: a value more than about 3 standard deviations from the mean is rare.

```python
column = data[:, 0]
z = (column - column.mean()) / column.std()
flagged = np.abs(z) > 3
print("flagged by the z-score rule on the first column:", int(flagged.sum()))
print("of those, truly planted:", int((flagged & (is_anomaly == 1)).sum()))
```

```output
flagged by the z-score rule on the first column: 9
of those, truly planted: 8
```

It flagged 9 points and caught all 8 planted ones, because every planted point is extreme in the first column too. But this rule looks at **one column at a time**, so it would miss a point that is unusual only because of the **combination** of values (a normal income with an impossible spending pattern). The next method looks at all columns together.

## Method 2: Isolation Forest (many columns)

The idea: anomalies are **easy to isolate**. Randomly split the data again and again with a forest of random trees; odd points end up alone after very few splits, normal points need many.

```python
from sklearn.ensemble import IsolationForest

forest = IsolationForest(n_estimators=200, contamination=0.02, random_state=0)
labels = forest.fit_predict(data)                  # -1 means anomaly, 1 means normal
flagged = labels == -1

caught = int((flagged & (is_anomaly == 1)).sum())
false_alarms = int((flagged & (is_anomaly == 0)).sum())
print("flagged in total:", int(flagged.sum()))
print(f"planted anomalies caught: {caught} of {int(is_anomaly.sum())}")
print("normal points wrongly flagged:", false_alarms)
```

```output
flagged in total: 11
planted anomalies caught: 8 of 8
normal points wrongly flagged: 3
```

The forest looks at all columns together, so it also catches points that are unusual only in combination. It catches most or all of the planted points and raises a few false alarms, which is the usual trade-off.

## The contamination setting

`contamination` is your guess of the **share of anomalies**. It decides how many points get flagged:

```python
for contamination in (0.005, 0.02, 0.05):
    labels = IsolationForest(n_estimators=200, contamination=contamination, random_state=0).fit_predict(data)
    flagged = labels == -1
    print(f"contamination {contamination:<5}: flagged {int(flagged.sum()):>3}, caught {int((flagged & (is_anomaly == 1)).sum())} of 8, false alarms {int((flagged & (is_anomaly == 0)).sum())}")
```

```output
contamination 0.005: flagged   3, caught 3 of 8, false alarms 0
contamination 0.02 : flagged  11, caught 8 of 8, false alarms 3
contamination 0.05 : flagged  26, caught 8 of 8, false alarms 18
```

A small value flags few points (it may miss some), a large value catches everything but floods you with false alarms. Rather than only the yes/no label, use the **score** (`forest.score_samples(data)`) to rank points from most to least unusual, and review the top of the list.

## Other methods

| Method | Idea |
| --- | --- |
| **Local Outlier Factor** | compares a point's density with its neighbours', good for varied densities |
| **One-Class SVM** | learns a boundary around normal data |
| **Autoencoder** | a neural network that rebuilds normal data well and unusual data badly (the deep learning course) |
| **DBSCAN** | points left as noise (label −1) |
| **Time series methods** | flag values far from the forecast |

## Judging alerts

| Question | Why it matters |
| --- | --- |
| how many alerts per day can a person review? | choose a threshold you can act on |
| of the alerts, how many were real (**precision**)? | too many false alarms and people ignore them |
| of the real problems, how many did we catch (**recall**)? | a missed fraud costs money |
| does "normal" change over time? | retrain, because habits and seasons drift |

:::warning
An anomaly is **unusual**, not necessarily **bad**. A huge purchase on a wedding day is rare but fine. Treat alerts as candidates for human review, and never block or punish people automatically on a score alone.
:::

:::interview
**Interviewers often ask:** "How does Isolation Forest work?" It builds random trees that split the data at random points. Anomalies are few and different, so they are isolated in very few splits, while normal points need many. The average number of splits gives an anomaly score.
:::
