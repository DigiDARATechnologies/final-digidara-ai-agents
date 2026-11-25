---
title: Distributions and sampling
summary: The normal distribution, the 68-95-99.7 rule, and why sample averages behave so well (the central limit theorem).
takeaways:
- A distribution shows how likely each value is
- The normal distribution is the bell curve: about 68% of values are within 1 standard deviation of the mean
- Averages of many samples are close to normal, even when the data is not
---
## The normal distribution

Heights, exam marks and measurement errors often follow a **bell curve**: most values near the middle, fewer further out, symmetric on both sides. It is described by two numbers: the mean and the standard deviation.

```python
import numpy as np
from scipy import stats

rng = np.random.default_rng(1)
marks = rng.normal(loc=60, scale=10, size=100_000)

print("mean:", round(marks.mean(), 2), " std:", round(marks.std(), 2))
for k in (1, 2, 3):
    share = ((marks > 60 - k * 10) & (marks < 60 + k * 10)).mean()
    print(f"within {k} std: {share:.3f}")
```

```output
mean: 59.95  std: 9.97
within 1 std: 0.684
within 2 std: 0.955
within 3 std: 0.997
```

:::formula
**The 68-95-99.7 rule:** about 68% of values lie within 1 standard deviation of the mean, 95% within 2, and 99.7% within 3.
:::

## Probabilities from the curve

If marks are normal with mean 60 and standard deviation 10, what share score above 75?

```python
dist = stats.norm(loc=60, scale=10)
print("P(marks > 75):", round(1 - dist.cdf(75), 4))
print("P(50 < marks < 70):", round(dist.cdf(70) - dist.cdf(50), 4))
print("marks needed for the top 10%:", round(dist.ppf(0.90), 1))
```

```output
P(marks > 75): 0.0668
P(50 < marks < 70): 0.6827
marks needed for the top 10%: 72.8
```

`cdf(x)` is the probability of being **below** x. `ppf(p)` goes the other way: the value with probability p below it.

## Z-scores

A **z-score** says how many standard deviations a value is from the mean. It lets you compare things on different scales:

```python
score_maths = (82 - 70) / 8       # maths: mean 70, std 8
score_english = (75 - 60) / 5     # English: mean 60, std 5
print(score_maths, score_english)
```

```output
1.5 3.0
```

An 82 in maths is 1.5 standard deviations above average, but a 75 in English is 3.0 above average, so the English result is more exceptional.

## Sampling

We rarely have all the data. We take a **sample** and use it to learn about the whole **population**. A good sample is **random**, so each member has an equal chance.

```python
rng = np.random.default_rng(2)
population = rng.normal(170, 8, size=50_000)           # heights of 50,000 people
sample = rng.choice(population, size=100, replace=False)
print("population mean:", round(population.mean(), 2))
print("sample mean    :", round(sample.mean(), 2))
```

```output
population mean: 170.02
sample mean    : 171.68
```

## The central limit theorem

Here is a remarkable fact. Even if the data is **not** normal, the **averages of many samples** form a bell curve.

```python
rng = np.random.default_rng(3)
skewed = rng.exponential(scale=10, size=100_000)         # strongly skewed data
print("skewness of the data:", round(stats.skew(skewed), 2))

sample_means = np.array([rng.choice(skewed, size=50).mean() for _ in range(2000)])
print("skewness of the sample means:", round(stats.skew(sample_means), 2))
print("mean of means:", round(sample_means.mean(), 2), " data mean:", round(skewed.mean(), 2))
```

```output
skewness of the data: 1.97
skewness of the sample means: 0.35
mean of means: 10.0  data mean: 10.02
```

The data is heavily skewed (about 2.0), but the sample means are much closer to symmetric (about 0.35), and they centre on the true mean. This is why statistics based on averages work on all kinds of data.

:::formula
**Standard error** = standard deviation / √(sample size)

A bigger sample gives a more precise average: the error shrinks with the square root of the sample size.
:::

```python
print("predicted standard error:", round(skewed.std() / 50 ** 0.5, 2))
print("observed spread of means:", round(sample_means.std(), 2))
```

```output
predicted standard error: 1.41
observed spread of means: 1.4
```
