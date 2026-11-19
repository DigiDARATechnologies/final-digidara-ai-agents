---
title: Statistics and axes
summary: Sum, mean, spread, percentiles and sorting, and how the axis argument works on a table.
takeaways:
- sum, mean, std, min and max summarise an array
- axis=0 works down the columns; axis=1 works across the rows
- percentile and median handle outliers better than the mean
---
## Summary numbers

```python
import numpy as np

marks = np.array([92, 78, 85, 66, 88, 71])
print("sum   :", marks.sum())
print("mean  :", round(marks.mean(), 2))
print("median:", np.median(marks))
print("std   :", round(marks.std(), 2))
print("min/max:", marks.min(), marks.max())
```

```output
sum   : 480
mean  : 80.0
median: 81.5
std   : 9.26
min/max: 66 92
```

The **standard deviation** (`std`) tells you how spread out the values are around the mean. A small std means they are close together.

## Percentiles

```python
print(np.percentile(marks, [25, 50, 75]))
```

```output
[72.75 81.5  87.25]
```

The 25th percentile is the value that 25% of the marks fall below. The 50th percentile is the median.

## Sorting

```python
print(np.sort(marks))
print(np.argsort(marks))            # the positions that would sort it
print(marks[np.argsort(marks)[::-1][:3]])   # the top 3 marks
```

```output
[66 71 78 85 88 92]
[3 5 1 2 4 0]
[92 88 85]
```

## The axis argument

On a table, you decide whether to calculate **down the columns** or **across the rows**.

```python
scores = np.array([
    [90, 80, 70],     # Asha:  maths, physics, chemistry
    [60, 75, 85],     # Ravi
    [88, 92, 79],     # Meena
])
print("all items       :", scores.mean())
print("per subject (axis=0):", scores.mean(axis=0))
print("per student (axis=1):", scores.mean(axis=1).round(1))
```

```output
all items       : 79.88888888888889
per subject (axis=0): [79.33333333 82.33333333 78.        ]
per student (axis=1): [80.  73.3 86.3]
```

| `axis=` | Direction | Gives you |
| --- | --- | --- |
| none | everything | one number |
| `0` | down the rows | one result per **column** |
| `1` | across the columns | one result per **row** |

:::tip
A way to remember: the axis you name is the one that **disappears**. `axis=0` removes the rows, leaving one value per column. The shape of the result confirms it: `(3, 3)` with `axis=0` becomes `(3,)`.
:::

## Cumulative and difference

```python
sales = np.array([100, 150, 120, 200])
print(np.cumsum(sales))
print(np.diff(sales))
print(np.corrcoef([1, 2, 3, 4], [2, 4, 5, 9])[0, 1].round(3))
```

```output
[100 250 370 570]
[ 50 -30  80]
0.965
```

`cumsum` is a running total, `diff` is the change from one item to the next, and `corrcoef` measures how two series move together.

:::interview
**Interviewers often ask:** "What does `axis=0` mean?" It performs the operation **along** the first axis, which for a 2D array means down the rows, giving one result for each column. `axis=1` gives one result for each row.
:::
