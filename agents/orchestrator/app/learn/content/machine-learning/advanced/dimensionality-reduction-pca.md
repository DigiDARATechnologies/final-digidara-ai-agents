---
title: Dimensionality reduction and PCA
summary: Shrink many features into a few that keep most of the information, with PCA, and know when and why to do it.
takeaways:
- PCA finds new directions (components) that capture the most variance, ordered from most to least
- Scale the data first; keep enough components to explain the variance you need
- PCA helps with noise, speed and visualisation, but the new features are harder to explain
---
## The curse of too many features

Images, sensors and text produce hundreds or thousands of columns, and many of them carry the same information (neighbouring pixels look alike). Too many features cause slow training, noise, overfitting, and make plotting impossible. **Dimensionality reduction** replaces many columns with a few that keep most of the information.

## PCA in plain words

Imagine a cloud of points shaped like a long, thin cigar tilted in the air. Most of the variation lies along one line, the cigar's length. **Principal Component Analysis (PCA)** finds that line (component 1), then the next most important direction at right angles to it (component 2), and so on. If you keep only the first few directions, you keep most of the shape with far fewer numbers.

| Term | Meaning |
| --- | --- |
| **component** | a new feature: a weighted mix of the original columns |
| **explained variance ratio** | the share of the data's total variation that a component carries |
| components are **uncorrelated** | each one adds new information |

## Hands-on with handwritten digits

The `digits` data has 1,797 images of 8 by 8 pixels: **64 features** each.

```python
import numpy as np
from sklearn.datasets import load_digits
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

digits = load_digits()
X, y = digits.data, digits.target
print(X.shape)

X_scaled = StandardScaler().fit_transform(X)
pca = PCA().fit(X_scaled)

cumulative = np.cumsum(pca.explained_variance_ratio_)
print("first 3 components explain:", np.round(pca.explained_variance_ratio_[:3], 3))
for target in (0.80, 0.90, 0.95):
    needed = int(np.argmax(cumulative >= target)) + 1
    print(f"{int(target * 100)}% of the variance needs {needed} of 64 components")
```

```output
(1797, 64)
first 3 components explain: [0.12  0.096 0.084]
80% of the variance needs 21 of 64 components
90% of the variance needs 31 of 64 components
95% of the variance needs 40 of 64 components
```

About half of the 64 numbers (31) are enough to keep 90% of the information. The pixels were highly redundant. `PCA(n_components=0.95)` picks the number for you.

## Does it still classify well?

```python
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import make_pipeline

full = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
reduced = make_pipeline(StandardScaler(), PCA(n_components=0.95), LogisticRegression(max_iter=2000))
tiny = make_pipeline(StandardScaler(), PCA(n_components=10), LogisticRegression(max_iter=2000))

for name, model in (("all 64 features", full), ("PCA, 95% variance", reduced), ("PCA, 10 components", tiny)):
    score = cross_val_score(model, X, y, cv=5).mean()
    print(f"{name:<20} accuracy {score:.3f}")

reduced.fit(X, y)
print("components kept by the 95% rule:", reduced.named_steps["pca"].n_components_)
```

```output
all 64 features      accuracy 0.920
PCA, 95% variance    accuracy 0.912
PCA, 10 components   accuracy 0.840
components kept by the 95% rule: 40
```

With far fewer features, accuracy stays close to the full-feature model, and even **10 components** (down from 64) do reasonably well. PCA sits **inside the pipeline** so it is fitted only on each training fold, avoiding leakage.

## Visualising in two dimensions

```python
points = PCA(n_components=2).fit_transform(X_scaled)
print(points.shape)
for digit in (0, 1, 4):
    centre = points[y == digit].mean(axis=0)
    print(f"digit {digit}: average position ({centre[0]:.1f}, {centre[1]:.1f})")
```

```output
(1797, 2)
digit 0: average position (-1.6, -1.9)
digit 1: average position (-0.5, 0.5)
digit 4: average position (-4.6, -0.4)
```

Plot `points` as a scatter coloured by `y` and similar digits form groups; the three digits above sit in clearly different places. This is the quickest way to "see" high-dimensional data.

## Rules of thumb

| Rule | Why |
| --- | --- |
| **scale first** (`StandardScaler`) | otherwise large-valued columns dominate the components |
| fit PCA on **training** data only | avoid leakage (use a pipeline) |
| choose components by **explained variance** (90 to 99%) or by validation score | keeps the information you need |
| PCA is **linear** | it cannot unfold curved shapes |
| components are mixtures | they are hard to explain to a business user |
| not always needed | trees and boosting cope with many features without PCA |

## Other methods

| Method | Used for |
| --- | --- |
| **t-SNE** | 2D pictures of clusters; for **visualisation only** (distances between far clusters mean little) |
| **UMAP** | similar pictures, faster, keeps more global structure |
| **autoencoders** | neural networks that squeeze data into a small code (the deep learning course) |
| **feature selection** (`SelectKBest`, Lasso, tree importance) | **drops** columns instead of mixing them, keeping them explainable |

:::warning
t-SNE and UMAP pictures are for exploring, not for measuring. Do not feed t-SNE output into a model, and do not read too much into distances or cluster sizes in the plot.
:::

:::interview
**Interviewers often ask:** "What is PCA and when would you use it?" A linear technique that rotates the data into uncorrelated components ordered by how much variance they carry, so you keep the first few. Use it to reduce noise and dimensionality, speed up training and visualise data; scale features first, fit it on training data only, and remember the components are less interpretable.
:::
