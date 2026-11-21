---
title: Probability, distributions, correlation and covariance
summary: Understand chance, the normal distribution, and how correlation and covariance measure whether two things move together.
takeaways:
- Probability is a number from 0 to 1; models output probabilities
- Many measurements follow the bell-shaped normal distribution
- Correlation measures a linear link between two variables, but never proves cause
---
## Probability

A **probability** is a number from 0 (impossible) to 1 (certain). `P(event) = favourable outcomes / all outcomes` when each is equally likely.

```python
print("a fair die shows 6:", round(1 / 6, 3))
print("a fair coin shows heads twice in a row:", 0.5 * 0.5)

# P(A or B) for events that cannot both happen: add; P(A and B) for independent events: multiply
print("a die shows 1 or 2:", round(1 / 6 + 1 / 6, 3))
```

```output
a fair die shows 6: 0.167
a fair coin shows heads twice in a row: 0.25
a die shows 1 or 2: 0.333
```

| Rule | Formula |
| --- | --- |
| not A | `1 − P(A)` |
| A and B (independent) | `P(A) × P(B)` |
| A or B (cannot both happen) | `P(A) + P(B)` |
| A given B (conditional) | `P(A and B) / P(B)` |

## Conditional probability and Bayes

A medical test is 95% accurate for people who have a disease, and wrongly flags 5% of healthy people. The disease affects 1% of people. **If someone tests positive, how likely is it that they have the disease?**

```python
p_disease = 0.01
p_positive_given_disease = 0.95
p_positive_given_healthy = 0.05

p_positive = p_positive_given_disease * p_disease + p_positive_given_healthy * (1 - p_disease)
p_disease_given_positive = p_positive_given_disease * p_disease / p_positive       # Bayes' rule

print("chance of testing positive:", round(p_positive, 4))
print("chance of having the disease after a positive test:", round(p_disease_given_positive, 3))
```

```output
chance of testing positive: 0.059
chance of having the disease after a positive test: 0.161
```

Surprisingly, it is only about 16%, not 95%. Because the disease is rare, most positive tests come from the many healthy people. This is **Bayes' rule**, the idea behind Naive Bayes in machine learning, and a reason to read accuracy together with how common something is.

## The normal distribution

Many things (heights, test marks, measurement errors) cluster around an average in a symmetric **bell shape**. It is described by two numbers: the **mean** (centre) and the **standard deviation** (spread).

```python
import numpy as np

rng = np.random.default_rng(0)
heights = rng.normal(loc=165, scale=8, size=100_000)

for k in (1, 2, 3):
    share = np.mean(np.abs(heights - 165) <= k * 8)
    print(f"within {k} standard deviation(s): {share:.1%}")
```

```output
within 1 standard deviation(s): 68.4%
within 2 standard deviation(s): 95.5%
within 3 standard deviation(s): 99.7%
```

The **68-95-99.7 rule**: about 68% of values lie within 1 standard deviation of the mean, 95% within 2 and 99.7% within 3. A value more than 3 standard deviations away is rare, which is why it is used to flag outliers.

A **z-score** says how many standard deviations a value is from the mean: `z = (x − mean) / std`. Standard scaling in ML is exactly this.

```python
x = 181
print("z-score of a height of 181 cm:", (x - 165) / 8)
```

```output
z-score of a height of 181 cm: 2.0
```

## Other distributions you will meet

| Distribution | Describes | Example |
| --- | --- | --- |
| **Uniform** | every value equally likely | a fair die |
| **Binomial** | number of successes in n tries | heads in 10 coin tosses |
| **Poisson** | counts of events in a period | calls to a help desk per hour |
| **Exponential** | time until the next event | minutes until the next customer |

## Covariance and correlation

Do two things move together? **Covariance** shows the direction; **correlation** rescales it to a number from −1 to +1.

```python
hours = np.array([1, 2, 3, 4, 5, 6])
marks = np.array([35, 48, 55, 66, 74, 85])
phone = np.array([8, 7, 7, 5, 4, 3])

print("covariance of hours and marks:", round(np.cov(hours, marks)[0, 1], 1))
print("correlation, hours vs marks  :", round(np.corrcoef(hours, marks)[0, 1], 3))
print("correlation, phone vs marks  :", round(np.corrcoef(phone, marks)[0, 1], 3))
```

```output
covariance of hours and marks: 33.9
correlation, hours vs marks  : 0.998
correlation, phone vs marks  : -0.98
```

| Correlation | Meaning |
| --- | --- |
| near +1 | both rise together |
| near 0 | no straight-line link |
| near −1 | one rises as the other falls |

:::warning
Correlation is **not** causation. Ice-cream sales and drownings both rise in summer, but one does not cause the other. Correlation also only sees straight-line links.
:::

:::interview
**Interviewers often ask:** "What is the difference between covariance and correlation?" Covariance shows the direction of a relationship but its size depends on the units; correlation divides by the standard deviations so it always lies between −1 and +1 and can be compared.
:::
