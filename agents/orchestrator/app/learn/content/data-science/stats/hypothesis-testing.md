---
title: Hypothesis testing and A/B tests
summary: Decide whether a difference is real or just chance, using the t-test, p-values and a chi-square test.
takeaways:
- A hypothesis test asks "could this difference be just chance?"
- A small p-value (below 0.05) is evidence against "nothing is going on"
- A p-value is not the probability that your idea is true
---
## Real difference, or luck?

You change a website button from grey to green. Green gets more clicks. Is it better, or did you just get lucky? A **hypothesis test** answers that question.

The idea:

1. State the **null hypothesis (H0)**: "there is no real difference."
2. Collect data and calculate how surprising it would be **if H0 were true**. That probability is the **p-value**.
3. If the p-value is very small (conventionally below **0.05**), the data would be rare under H0, so you **reject H0**.

## A t-test: comparing two averages

Two teaching methods were tried on two groups of students. Did the method make a difference?

```python
import numpy as np
from scipy import stats

rng = np.random.default_rng(8)
method_a = rng.normal(loc=70, scale=10, size=40)
method_b = rng.normal(loc=76, scale=10, size=40)

print("mean A:", round(method_a.mean(), 1), " mean B:", round(method_b.mean(), 1))
result = stats.ttest_ind(method_a, method_b)
print("t =", round(result.statistic, 2), " p =", round(result.pvalue, 4))
```

```output
mean A: 68.3  mean B: 77.3
t = -3.59  p = 0.0006
```

The p-value is small, so a gap this large would be unlikely if both methods were equally good. We reject H0 and say the methods **differ**.

## What a p-value is not

| A p-value of 0.03 means | It does **not** mean |
| --- | --- |
| if there were no real difference, you would see a result this extreme about 3% of the time | there is a 97% chance your idea is right |

:::warning
"Statistically significant" is not the same as "important". With a huge sample, a tiny difference can have a very small p-value. Always look at the **size** of the difference too.
:::

## Confidence interval

A p-value says whether. A **confidence interval** says how big:

```python
difference = method_b.mean() - method_a.mean()
std_error = (method_a.var(ddof=1) / 40 + method_b.var(ddof=1) / 40) ** 0.5
low, high = difference - 1.96 * std_error, difference + 1.96 * std_error
print(f"difference: {difference:.1f} marks, 95% interval: {low:.1f} to {high:.1f}")
```

```output
difference: 8.9 marks, 95% interval: 4.1 to 13.8
```

If the interval does not include 0, that agrees with the test: the methods differ, and the interval shows by roughly how much.

## A/B test on clicks: the chi-square test

For yes/no outcomes (clicked or not), compare counts:

```python
table = np.array([
    [120, 880],     # grey button: 120 clicks, 880 no click
    [160, 840],     # green button: 160 clicks, 840 no click
])
chi2, p, dof, expected = stats.chi2_contingency(table)
print("click rates:", table[0, 0] / table[0].sum(), table[1, 0] / table[1].sum())
print("p =", round(p, 4))
```

```output
click rates: 0.12 0.16
p = 0.012
```

## Two kinds of mistake

| | In reality: no effect | In reality: there is an effect |
| --- | --- | --- |
| **You say there is an effect** | **Type I error** (false alarm) | correct |
| **You say there is none** | correct | **Type II error** (a miss) |

The 0.05 limit means you accept about a 5% chance of a Type I error when nothing is going on.

## A good A/B test

- Decide the question and the measure **before** you look at results.
- Split users **randomly** into the two groups.
- Decide the sample size in advance, and do not stop early because it "looks good".
- Test one change at a time.

:::interview
**Interviewers often ask:** "What is a p-value?" The probability of seeing a result at least as extreme as the one observed, **assuming the null hypothesis is true**. A small p-value is evidence against the null, not proof of your idea.
:::
