---
title: Statistics essentials
summary: Summarise data with mean, median, mode, variance and standard deviation, and know which summary to trust.
takeaways:
- Mean, median and mode describe the centre; variance and standard deviation describe the spread
- Outliers pull the mean but barely move the median
- Standard deviation says how far values typically sit from the average
---
## Describing the centre

| Measure | What it is | Best when |
| --- | --- | --- |
| **Mean** | the sum divided by the count | data is fairly even |
| **Median** | the middle value when sorted | there are outliers or skew |
| **Mode** | the most common value | categories, or repeated values |

```python
import numpy as np
import statistics

marks = [92, 48, 85, 71, 64, 55, 71]

print("mean  :", round(np.mean(marks), 2))
print("median:", np.median(marks))
print("mode  :", statistics.mode(marks))
```

```output
mean  : 69.43
median: 71.0
mode  : 71
```

## Outliers: when the mean misleads

```python
salaries = [30, 32, 35, 36, 38, 40, 400]        # in thousands: one very large value

print("mean  :", round(np.mean(salaries), 1))
print("median:", np.median(salaries))
```

```output
mean  : 87.3
median: 36.0
```

One huge salary drags the mean far above what most people earn, but the median stays with the typical person. Always check both.

## Describing the spread

Two classes can have the same average and very different results.

```python
class_a = [68, 70, 72, 70, 70]
class_b = [40, 100, 55, 95, 60]

for name, data in (("A", class_a), ("B", class_b)):
    print(f"class {name}: mean {np.mean(data):.0f}, range {max(data) - min(data)}, variance {np.var(data):.1f}, std {np.std(data):.1f}")
```

```output
class A: mean 70, range 4, variance 1.6, std 1.3
class B: mean 70, range 60, variance 550.0, std 23.5
```

| Measure | Meaning |
| --- | --- |
| **Range** | largest minus smallest |
| **Variance** | the average of the squared distances from the mean |
| **Standard deviation** | the square root of the variance, in the same units as the data |

Both classes average 70, but class B's standard deviation is far larger, so its students are very different from each other.

## Quartiles and the five-number summary

```python
data = [48, 55, 64, 71, 71, 85, 92]
q1, q2, q3 = np.percentile(data, [25, 50, 75])
print("minimum :", min(data))
print("Q1      :", q1)
print("median  :", q2)
print("Q3      :", q3)
print("maximum :", max(data))
print("IQR (Q3 - Q1):", q3 - q1)
```

```output
minimum : 48
Q1      : 59.5
median  : 71.0
Q3      : 78.0
maximum : 92
IQR (Q3 - Q1): 18.5
```

The **IQR** (interquartile range) is the spread of the middle half of the data. A common outlier rule marks values below `Q1 − 1.5 × IQR` or above `Q3 + 1.5 × IQR`.

## Population and sample

| | Formula divides by | Used when |
| --- | --- | --- |
| population standard deviation | n | you have **everyone** |
| sample standard deviation | n − 1 | you have **a sample** (almost always) |

```python
print("population std:", round(np.std(data), 3))
print("sample std    :", round(np.std(data, ddof=1), 3))
```

```output
population std: 14.411
sample std    : 15.566
```

NumPy's `std` divides by `n` by default; pandas `.std()` uses the sample version. Knowing which one a tool uses avoids confusion.

:::interview
**Interviewers often ask:** "When do you use the median instead of the mean?" When the data has outliers or is skewed (salaries, house prices), because the median is not pulled by extreme values.
:::
