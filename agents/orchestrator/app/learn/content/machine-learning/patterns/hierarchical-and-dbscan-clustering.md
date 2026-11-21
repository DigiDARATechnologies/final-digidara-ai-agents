---
title: Hierarchical clustering and DBSCAN
summary: Go beyond K-Means: build clusters step by step with hierarchical clustering, and find clusters of any shape, plus noise, with DBSCAN.
takeaways:
- Hierarchical clustering merges the closest groups step by step, so you can choose the number of clusters later
- DBSCAN finds dense regions of any shape and marks lonely points as noise
- K-Means assumes round, similar-sized clusters, which is not always true
---
## K-Means has limits

K-Means looks for round clusters of similar size, and you must choose the number of clusters first. Real data is often curved or uneven, and you may not know how many groups there are. Two more tools help.

## Hierarchical (agglomerative) clustering

Start with **every point as its own cluster**. Repeatedly **merge the two closest clusters** until one remains. The merges form a tree called a **dendrogram**. Cut the tree at any height to get any number of clusters.

```python
import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage

# six students described by (study hours, marks)
points = np.array([[1, 35], [1.5, 40], [2, 42], [6, 80], [6.5, 85], [7, 88]], dtype=float)

merges = linkage(points, method="ward")
print("each row: [cluster A, cluster B, distance, size of the new cluster]")
print(np.round(merges, 1))

for k in (2, 3):
    print(f"cut into {k} clusters:", fcluster(merges, t=k, criterion="maxclust"))
```

```output
each row: [cluster A, cluster B, distance, size of the new cluster]
[[ 1.   2.   2.1  2. ]
 [ 4.   5.   3.   2. ]
 [ 0.   6.   7.   3. ]
 [ 3.   7.   7.6  3. ]
 [ 8.   9.  79.   6. ]]
cut into 2 clusters: [1 1 1 2 2 2]
cut into 3 clusters: [1 1 1 3 2 2]
```

The first merges join the closest students; the last merge (the largest distance) joins the low-marks group with the high-marks group. A **big jump** in merge distance is a hint to cut just before it.

| Linkage (how to measure distance between clusters) | Behaviour |
| --- | --- |
| **ward** | merges that grow total spread the least; compact, even clusters (a good default) |
| **average** | the average distance between all pairs |
| **single** | the closest pair; can chain points into long strings |
| **complete** | the farthest pair; compact clusters |

You can draw the tree with `scipy.cluster.hierarchy.dendrogram(merges)` to see where to cut.

## DBSCAN: density, shape and noise

**DBSCAN** groups points that are **densely packed together** and marks points in empty regions as **noise**. It needs no number of clusters. Two settings:

| Setting | Meaning |
| --- | --- |
| `eps` | how close counts as "neighbours" |
| `min_samples` | how many neighbours make a dense region |

## Curved clusters: three methods compared

```python
from sklearn.cluster import DBSCAN, AgglomerativeClustering, KMeans
from sklearn.datasets import make_moons
from sklearn.metrics import adjusted_rand_score

X, true_groups = make_moons(n_samples=300, noise=0.07, random_state=0)

results = {
    "K-Means (k=2)": KMeans(n_clusters=2, n_init=10, random_state=0).fit_predict(X),
    "Hierarchical (ward)": AgglomerativeClustering(n_clusters=2, linkage="ward").fit_predict(X),
    "Hierarchical (single)": AgglomerativeClustering(n_clusters=2, linkage="single").fit_predict(X),
    "DBSCAN": DBSCAN(eps=0.2, min_samples=5).fit_predict(X),
}
for name, labels in results.items():
    print(f"{name:<22} agreement with the true moons: {adjusted_rand_score(true_groups, labels):.2f}")
```

```output
K-Means (k=2)          agreement with the true moons: 0.23
Hierarchical (ward)    agreement with the true moons: 0.40
Hierarchical (single)  agreement with the true moons: 1.00
DBSCAN                 agreement with the true moons: 1.00
```

The agreement score runs from about 0 (random) to 1 (perfect). K-Means and ward linkage cut the two moons straight across, so they score poorly. **DBSCAN** (and single linkage) follow the curve and recover the moons almost perfectly, because they chain neighbouring points instead of looking for round blobs.

## Noise points

```python
labels = results["DBSCAN"]
print("clusters found:", len(set(labels) - {-1}))
print("points marked as noise (label -1):", int((labels == -1).sum()))
```

```output
clusters found: 2
points marked as noise (label -1): 0
```

These moons are clean and dense, so DBSCAN found no noise here. On messier data, DBSCAN labels lonely points `-1` (noise) instead of forcing them into a cluster, which makes it useful for **spotting outliers** too.

## Choosing eps

| Symptom | Fix |
| --- | --- |
| everything is one big cluster | `eps` too large: reduce it |
| almost everything is noise | `eps` too small: increase it |
| a common method | plot each point's distance to its k-th nearest neighbour and pick `eps` at the "elbow" |

**Scale your features first**: both methods use distances.

## Which one to use

| Method | Choose it when |
| --- | --- |
| **K-Means** | round, similar-sized groups; large data; you know k |
| **Hierarchical** | small data; you want the tree; you want to decide k afterwards |
| **DBSCAN** | odd shapes; unknown number of clusters; you want noise flagged |

:::interview
**Interviewers often ask:** "K-Means or DBSCAN?" K-Means needs the number of clusters and finds round clusters. DBSCAN needs a neighbourhood size, finds clusters of any shape, and marks outliers as noise, but struggles when densities differ a lot.
:::
