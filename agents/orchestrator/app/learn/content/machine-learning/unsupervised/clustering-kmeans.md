---
title: Clustering with K-means
summary: Find groups in data that has no labels, choose the number of clusters, and check the result.
takeaways:
- Clustering groups similar rows without any labels
- K-means needs you to choose k, the number of groups
- The silhouette score helps choose k
---
## Groups without labels

So far every row had a correct answer. **Unsupervised learning** has none: the model looks for **structure** by itself. The most common task is **clustering**: grouping rows that are similar.

Uses: grouping customers by behaviour, grouping news articles by topic, finding similar products.

## K-means

**K-means** picks `k` centre points, assigns every row to its nearest centre, moves each centre to the middle of its group, and repeats until nothing changes.

```python
from sklearn.cluster import KMeans
from sklearn.datasets import make_blobs

X, true_groups = make_blobs(n_samples=300, centers=3, cluster_std=0.6, random_state=42)

km = KMeans(n_clusters=3, n_init=10, random_state=42)
labels = km.fit_predict(X)

print(labels[:10])
print(km.cluster_centers_.round(2))
```

```output
[1 1 0 2 1 2 0 2 0 0]
[[-2.58  9.03]
 [-6.88 -6.94]
 [ 4.7   2.  ]]
```

`labels` says which cluster (0, 1 or 2) each row belongs to, and `cluster_centers_` are the middles of the three groups.

## How many clusters?

In real life you do not know `k`. Try several values and compare the **silhouette score**, which measures how well each row fits its own cluster compared with the next nearest one. It runs from -1 to 1, and higher is better.

```python
from sklearn.metrics import silhouette_score

for k in range(2, 7):
    model = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
    print(f"k={k}  silhouette={silhouette_score(X, model.labels_):.3f}  inertia={model.inertia_:.0f}")
```

```output
k=2  silhouette=0.736  inertia=5335
k=3  silhouette=0.908  inertia=204
k=4  silhouette=0.704  inertia=179
k=5  silhouette=0.518  inertia=154
k=6  silhouette=0.327  inertia=131
```

The highest silhouette tells you the best `k`: here it is 3, which matches how the data was made. With messier real data the best value is often less clear, so combine it with common sense. **Inertia** is the total squared distance from each row to its centre, and it always shrinks as `k` grows. People look for the "elbow", the `k` after which it stops dropping quickly.

## A customer example

```python
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

customers = pd.DataFrame({
    "yearly_spend": [200, 220, 250, 1800, 2000, 1900, 800, 760, 820, 210],
    "visits_per_month": [2, 3, 2, 12, 14, 13, 6, 7, 6, 3],
})
scaled = StandardScaler().fit_transform(customers)
customers["segment"] = KMeans(n_clusters=3, n_init=10, random_state=0).fit_predict(scaled)
print(customers.groupby("segment").mean().round(0))
```

```output
         yearly_spend  visits_per_month
segment
0              1900.0              13.0
1               220.0               2.0
2               793.0               6.0
```

Three kinds of customer appear: low, medium and high spenders. The numbers on the segment labels (0, 1, 2) mean nothing by themselves. **You** name each group by looking at its averages.

:::warning
K-means uses distances, so **scale your features** first, as above. It also assumes roughly round groups of similar size, and it can give a different answer if the starting centres change, so keep `n_init=10` and a `random_state`.
:::

:::interview
**Interviewers often ask:** "How do you choose k in K-means?" Try several values and use the elbow method on inertia and the silhouette score, then check that the groups make business sense.
:::
