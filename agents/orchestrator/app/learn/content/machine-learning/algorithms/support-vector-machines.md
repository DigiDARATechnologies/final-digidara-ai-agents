---
title: Support vector machines (SVM)
summary: Understand how an SVM draws the widest possible boundary between classes, how kernels bend it, and which two settings to tune.
takeaways:
- An SVM finds the boundary with the widest margin between two classes
- A kernel (such as RBF) lets it draw curved boundaries
- Scale the features, and tune C (how strict) and gamma (how wiggly)
---
## The idea: the widest street

Many lines can separate two groups of points. The **support vector machine** picks the one with the **widest gap (margin)** on both sides, like the widest possible street between two neighbourhoods. The few points that touch the edge of the street are the **support vectors**; only they decide where the line goes.

A wide margin usually means the model **generalises** better to new points.

## Curved boundaries: kernels

A straight line cannot separate two interlocking half-moons. A **kernel** lets the SVM draw a **curved** boundary without you creating new features.

```python
from sklearn.datasets import make_moons
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

X, y = make_moons(n_samples=300, noise=0.25, random_state=0)

for kernel in ("linear", "rbf"):
    model = make_pipeline(StandardScaler(), SVC(kernel=kernel))
    score = cross_val_score(model, X, y, cv=5).mean()
    print(f"{kernel:<7} kernel: cross-validated accuracy {score:.3f}")
```

```output
linear  kernel: cross-validated accuracy 0.837
rbf     kernel: cross-validated accuracy 0.953
```

The **linear** kernel is limited to a straight line, and the **RBF** kernel (the usual default) draws a curve, so it scores better on curved data.

## The two settings to tune

| Setting | Meaning | Too small | Too large |
| --- | --- | --- | --- |
| **C** | how strictly to avoid mistakes | a wide, forgiving margin (may underfit) | tries to classify every point (may overfit) |
| **gamma** (RBF) | how far one point's influence reaches | a smooth, simple curve (may underfit) | a wiggly boundary around single points (overfits) |

```python
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=0)

print("gamma   train accuracy   test accuracy")
for gamma in (0.1, 1, 10, 100):
    model = make_pipeline(StandardScaler(), SVC(kernel="rbf", gamma=gamma, C=10)).fit(X_train, y_train)
    print(f"{gamma:>5}   {model.score(X_train, y_train):>14.3f}   {model.score(X_test, y_test):>13.3f}")
```

```output
gamma   train accuracy   test accuracy
  0.1            0.890           0.856
    1            0.962           0.989
   10            0.981           0.956
  100            1.000           0.956
```

Read the table: a tiny gamma (0.1) is too smooth, so both scores are lower (**underfitting**). A gamma of 1 gives the best test accuracy (0.989). At gamma 100 the training accuracy reaches a perfect 1.000 but the test accuracy falls back to 0.956: the boundary wraps around individual points, which is **overfitting**. Choose C and gamma with cross-validation (`GridSearchCV`), not by guessing.

## Practical rules

| Rule | Why |
| --- | --- |
| **always scale** the features | SVM uses distances, so large-valued columns would dominate |
| start with the **RBF** kernel | works well on most problems |
| use **LinearSVC** for very large, high-dimensional data (text) | much faster |
| for probabilities use `SVC(probability=True)` | slower, but gives scores |

## When to use it

| Good for | Not great for |
| --- | --- |
| small to medium tables with clear boundaries | very large datasets (training gets slow) |
| high-dimensional data such as text | data with a lot of noise and overlap |
| a strong baseline | when you must explain the decision simply (a tree or logistic regression explains better) |

:::interview
**Interviewers often ask:** "What is the kernel trick?" It lets an SVM behave as if the data were mapped into a higher-dimensional space where a straight boundary separates the classes, without actually computing that space, so it can draw curved boundaries cheaply.
:::
