---
title: Descriptive statistics
summary: Summarise data with mean, median, mode, spread, percentiles and skewness, and know which to use.
takeaways:
- Mean, median and mode describe the centre; standard deviation and IQR describe the spread
- The median ignores extremes, the mean does not
- Skewness tells you whether the data leans to one side
---
## Describing the centre

```python
import numpy as np
import pandas as pd

marks = pd.Series([35, 40, 45, 50, 50, 55, 60, 65, 70, 95])
print("mean  :", marks.mean())
print("median:", marks.median())
print("mode  :", marks.mode().tolist())
```

```output
mean  : 56.5
median: 52.5
mode  : [50]
```

| Measure | What it is | Best for |
| --- | --- | --- |
| **Mean** | the sum divided by the count | symmetric data without outliers |
| **Median** | the middle value | skewed data, or data with outliers |
| **Mode** | the most common value | categories, or the most frequent number |

## Describing the spread

Two classes can have the same average and look very different:

```python
class_a = pd.Series([48, 49, 50, 51, 52])
class_b = pd.Series([10, 30, 50, 70, 90])
print(class_a.mean(), class_b.mean())
print("std:", round(class_a.std(), 2), round(class_b.std(), 2))
```

```output
50.0 50.0
std: 1.58 31.62
```

Same mean, very different **spread**. The standard deviation measures it.

| Measure | Meaning |
| --- | --- |
| **Range** | maximum minus minimum |
| **Variance** | the average squared distance from the mean |
| **Standard deviation** | the square root of the variance, in the original units |
| **IQR** | the range of the middle 50% (Q3 minus Q1), ignores extremes |

:::formula
**Standard deviation** = square root of the average of (value − mean)²

(For a sample, divide by n − 1 instead of n. Pandas does this by default; NumPy's `std` divides by n unless you pass `ddof=1`.)
:::

## Percentiles and quartiles

```python
print(marks.quantile([0.25, 0.5, 0.75]).tolist())
print(marks.describe().round(2))
```

```output
[46.25, 52.5, 63.75]
count    10.00
mean     56.50
std      17.33
min      35.00
25%      46.25
50%      52.50
75%      63.75
max      95.00
dtype: float64
```

The 25th, 50th and 75th percentiles are the **quartiles**. A box plot draws exactly these.

## Skewness: which way does the data lean?

```python
from scipy import stats

symmetric = pd.Series([1, 2, 3, 4, 5, 6, 7])
right_tail = pd.Series([20, 22, 25, 26, 28, 30, 90])      # a few very large values
print(round(stats.skew(symmetric), 2), round(stats.skew(right_tail), 2))
print("mean > median for right-skewed data:", right_tail.mean() > right_tail.median())
```

```output
0.0 1.96
mean > median for right-skewed data: True
```

| Skew | Shape | Mean vs median |
| --- | --- | --- |
| near 0 | balanced | about equal |
| positive | long tail to the right (salaries, house prices) | mean above median |
| negative | long tail to the left | mean below median |

:::remember
When people say "the average salary is ₹9 lakh", ask whether that is the **mean** or the **median**. A few very high salaries can pull the mean far above what a typical person earns.
:::
