---
title: Probability basics
summary: Measure how likely things are: simple probability, independent events, conditional probability and Bayes' rule.
takeaways:
- Probability = favourable outcomes divided by all outcomes, between 0 and 1
- For independent events, multiply the probabilities
- Bayes' rule updates a probability when you get new evidence
---
## What probability means

**Probability** measures how likely an event is, from 0 (impossible) to 1 (certain).

:::formula
P(event) = number of favourable outcomes / total number of equally likely outcomes
:::

Rolling a fair die, the chance of an even number is 3 out of 6:

```python
import numpy as np

print(3 / 6)

rng = np.random.default_rng(5)
rolls = rng.integers(1, 7, size=100_000)
print("simulated:", round((rolls % 2 == 0).mean(), 3))
```

```output
0.5
simulated: 0.5
```

A simulation with many rolls gets very close to the exact answer. This is the **law of large numbers**: more trials, closer to the true probability.

## Combining events

| Rule | Formula | Example |
| --- | --- | --- |
| **Not** | P(not A) = 1 − P(A) | P(not a six) = 1 − 1/6 |
| **And** (independent) | P(A and B) = P(A) × P(B) | two sixes in a row = 1/6 × 1/6 |
| **Or** (cannot both happen) | P(A or B) = P(A) + P(B) | a 1 or a 2 on one roll = 1/6 + 1/6 |

```python
print("two sixes:", round(1 / 6 * 1 / 6, 4))
print("at least one six in 3 rolls:", round(1 - (5 / 6) ** 3, 4))
```

```output
two sixes: 0.0278
at least one six in 3 rolls: 0.4213
```

"At least one" is easiest as **1 minus the chance of none**.

## Conditional probability

P(A given B) is the probability of A **once you know B happened**. Of 100 students, 60 passed maths and 40 of those also passed physics.

```python
passed_maths = 60
passed_both = 40
print("P(physics | maths) =", round(passed_both / passed_maths, 3))
```

```output
P(physics | maths) = 0.667
```

## Bayes' rule: updating with evidence

A disease affects 1% of people. A test finds 90% of people who have it (sensitivity), but also gives a **false alarm** for 5% of healthy people. You test positive. How likely is it that you really have the disease?

:::formula
P(disease | positive) = P(positive | disease) × P(disease) / P(positive)
:::

```python
prevalence = 0.01
sensitivity = 0.90
false_alarm = 0.05

p_positive = sensitivity * prevalence + false_alarm * (1 - prevalence)
p_disease_given_positive = sensitivity * prevalence / p_positive
print(round(p_positive, 4))
print(round(p_disease_given_positive, 3))
```

```output
0.0585
0.154
```

Only about **15%**. Most positive tests are false alarms, because there are so many more healthy people than sick people. This surprises almost everyone, and it is why a single test is rarely used to decide on its own.

You can see the same thing by counting, for 10,000 people:

| | Count |
| --- | --- |
| Sick (1%) | 100 |
| Sick and test positive (90%) | 90 |
| Healthy | 9,900 |
| Healthy and test positive (5%) | 495 |
| **All positives** | 585 |
| **Positives who are really sick** | 90 / 585 ≈ 15% |

:::interview
**Interviewers often ask:** a classic probability question about two dice, coins or a medical test like this one. Say the rule you are using (and, or, conditional) before you calculate. It shows your thinking.
:::
