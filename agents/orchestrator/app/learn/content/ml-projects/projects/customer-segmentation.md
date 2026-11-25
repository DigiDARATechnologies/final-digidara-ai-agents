---
title: Project: Customer segmentation (clustering)
summary: Group customers by their buying behaviour with RFM and K-Means, choose the number of groups, name them, and suggest an action for each.
takeaways:
- Segmentation finds groups of similar customers without any labels
- RFM (recency, frequency, monetary) describes buying behaviour with three numbers
- A segment is only useful if you can name it and act on it
---
## The problem

A shop has thousands of customers and sends them all the same offer. Better: **group customers by behaviour** and treat each group differently. There are no labels to learn from, so this is **unsupervised** learning.

## RFM: three numbers per customer

| Letter | Meaning | Question |
| --- | --- | --- |
| **R** (recency) | days since the last purchase | how recently did they buy? |
| **F** (frequency) | number of purchases | how often? |
| **M** (monetary) | total spent | how much? |

```python
import numpy as np
import pandas as pd

rng = np.random.default_rng(21)
parts = []
for size, recency, frequency, money in ((220, 12, 14, 18000), (260, 90, 3, 3500), (120, 200, 1, 800)):
    parts.append(pd.DataFrame({
        "recency": rng.gamma(4, recency / 4, size).round(0),
        "frequency": np.maximum(1, rng.poisson(frequency, size)),
        "monetary": rng.gamma(5, money / 5, size).round(-1),
    }))
customers = pd.concat(parts, ignore_index=True).sample(frac=1, random_state=0).reset_index(drop=True)

print(customers.shape)
print(customers.describe().round(0).to_string())
```

```output
(600, 3)
       recency  frequency  monetary
count    600.0      600.0     600.0
mean      83.0        7.0    7702.0
std       81.0        6.0    8080.0
min        2.0        1.0     170.0
25%       14.0        2.0    1845.0
50%       65.0        4.0    3795.0
75%      120.0       12.0   12232.0
max      560.0       28.0   41330.0
```

We hid three behaviours in the data (loyal big spenders, occasional buyers, and lapsed customers). A real analysis does not know the groups in advance, so let us see whether clustering finds them.

## Scale, then cluster

The three columns have very different ranges (days, counts, rupees), so scale them first or the rupees would dominate.

```python
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

scaled = StandardScaler().fit_transform(np.log1p(customers))       # log first: money and frequency are skewed

print("clusters   silhouette score")
for k in range(2, 7):
    labels = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(scaled)
    print(f"{k:>8}   {silhouette_score(scaled, labels):.3f}")
```

```output
clusters   silhouette score
       2   0.642
       3   0.531
       4   0.475
       5   0.319
       6   0.286
```

The **silhouette score** measures how well each customer fits its own group compared with the nearest other group (higher is better, up to 1). It is highest for 2 groups (0.64) and falls as groups are added. But two groups (active and inactive) is too coarse to plan marketing, and 3 groups still score well (0.53). So we choose **3**, using the score **and** common sense: a segment must be large enough to matter and different enough to act on. The score is a guide, not a command.

## Profile each segment

```python
best_k = 3
customers["segment"] = KMeans(n_clusters=best_k, n_init=10, random_state=0).fit_predict(scaled)

profile = customers.groupby("segment").agg(
    customers=("recency", "size"),
    avg_recency_days=("recency", "mean"),
    avg_purchases=("frequency", "mean"),
    avg_spend=("monetary", "mean"),
).round(0)
profile["share_%"] = (100 * profile["customers"] / len(customers)).round(0)
print(profile.sort_values("avg_spend", ascending=False).to_string())
```

```output
         customers  avg_recency_days  avg_purchases  avg_spend  share_%
segment
1              221              12.0           14.0    16534.0     37.0
0              250              94.0            3.0     3426.0     42.0
2              129             183.0            1.0      858.0     22.0
```

Read each row as a story. One group bought very recently, buys often and spends the most; another buys every now and then; the last has not bought for months and spent little.

## Name the segments and decide actions

| Segment (from the table) | Name | Action |
| --- | --- | --- |
| recent, frequent, high spend | **Loyal customers** | thank them, early access, a loyalty reward; do not discount heavily |
| middling on everything | **Occasional buyers** | reminders and offers to raise the frequency |
| long ago, few purchases, low spend | **Lapsed customers** | a win-back message; a small incentive; stop spending on them if they do not respond |

The **names and actions** are the real deliverable. A cluster number (0, 1, 2) means nothing to a marketing manager.

## See it in two dimensions

```python
from sklearn.decomposition import PCA

pca = PCA(n_components=2).fit(scaled)
print("share of the information kept in 2 dimensions:", round(float(pca.explained_variance_ratio_.sum()), 2))
points = pca.transform(scaled)
for segment in range(best_k):
    centre = points[customers["segment"] == segment].mean(axis=0)
    print(f"segment {segment}: centre at ({centre[0]:.1f}, {centre[1]:.1f})")
```

```output
share of the information kept in 2 dimensions: 0.95
segment 0: centre at (-0.7, 0.2)
segment 1: centre at (2.0, -0.1)
segment 2: centre at (-2.1, -0.3)
```

Plotting `points` coloured by segment (a scatter plot) shows the groups side by side. Here PCA keeps most of the information in two dimensions, so the picture is trustworthy.

## Checks and cautions

| Check | Why |
| --- | --- |
| rerun with another `random_state` | stable segments should not change much |
| are segments big enough to act on? | a tiny segment may not justify a campaign |
| refresh monthly | customers move between segments |
| use the segments in an experiment (A/B test) | prove the action works |
| do not use sensitive attributes for targeting | privacy and fairness |

:::interview
**Interviewers often ask:** "How do you choose the number of clusters?" Try several values and compare silhouette scores (and the elbow of the inertia), then check that the clusters are stable, large enough and meaningful for the business.
:::
