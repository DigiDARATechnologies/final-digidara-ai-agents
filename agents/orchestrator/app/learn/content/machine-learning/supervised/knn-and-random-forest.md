---
title: KNN and random forests
summary: Two popular models: K-nearest neighbours (ask your neighbours) and random forests (many trees voting).
takeaways:
- KNN predicts from the k most similar training rows
- A random forest averages many trees, which cancels out their mistakes
- Compare models on the same test split
---
## K-nearest neighbours

**KNN** has no training in the usual sense. To predict a new point, it finds the **k** closest training points and takes a vote. "You are like your neighbours."

```python
from sklearn.datasets import load_wine
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

wine = load_wine()
X_train, X_test, y_train, y_test = train_test_split(wine.data, wine.target, test_size=0.25, random_state=3, stratify=wine.target)

for k in [1, 3, 5, 11, 25]:
    knn = make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=k)).fit(X_train, y_train)
    print(f"k={k:2d}  test accuracy={knn.score(X_test, y_test):.3f}")
```

```output
k= 1  test accuracy=0.978
k= 3  test accuracy=0.978
k= 5  test accuracy=0.978
k=11  test accuracy=0.956
k=25  test accuracy=0.956
```

| k | Effect |
| --- | --- |
| small (1) | follows noise; can overfit |
| large | smoother, but can ignore real detail |

:::warning
KNN works with distances, so the features **must be scaled**, as done above. Without scaling, a feature with big numbers (such as salary) swamps the others.
:::

## Random forest: many trees vote

One tree can overfit. A **random forest** builds many trees, each on a random sample of the rows and a random choice of features, and lets them **vote**. Individual trees make different mistakes, and the vote cancels many of them out.

```python
from sklearn.ensemble import RandomForestClassifier

forest = RandomForestClassifier(n_estimators=200, random_state=3)
forest.fit(X_train, y_train)
print("forest test accuracy:", round(forest.score(X_test, y_test), 3))
```

```output
forest test accuracy: 0.956
```

## The strongest clues

```python
ranked = sorted(zip(wine.feature_names, forest.feature_importances_), key=lambda pair: pair[1], reverse=True)
for name, value in ranked[:4]:
    print(f"{name:22s} {value:.3f}")
```

```output
proline                0.202
color_intensity        0.159
flavanoids             0.151
hue                    0.113
```

## Comparing several models fairly

Use the **same split** for every model:

```python
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

models = {
    "Logistic regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
    "Decision tree": DecisionTreeClassifier(max_depth=3, random_state=3),
    "KNN (k=5)": make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=5)),
    "Random forest": RandomForestClassifier(n_estimators=200, random_state=3),
}
for name, m in models.items():
    print(f"{name:20s} {m.fit(X_train, y_train).score(X_test, y_test):.3f}")
```

```output
Logistic regression  1.000
Decision tree        0.933
KNN (k=5)            0.978
Random forest        0.956
```

:::tip
There is no best model for everything. Start with a simple one (logistic regression), then try a random forest, and keep whichever is better **on test data** and simple enough to explain.
:::

:::interview
**Interviewers often ask:** "Why does a random forest overfit less than one decision tree?" Each tree sees a random sample of rows and features, so the trees are different. Averaging their votes reduces the variance of the result.
:::
