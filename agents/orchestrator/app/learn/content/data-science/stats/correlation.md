---
title: Correlation and causation
summary: Measure how two columns move together with correlation, and learn why correlation is not causation.
takeaways:
- Correlation runs from -1 to 1 and measures a straight-line relationship
- Spearman correlation works for curved but steadily rising relationships
- Two things moving together does not mean one causes the other
---
## Do two things move together?

**Correlation** measures how strongly two numbers move together.

```python
import numpy as np
import pandas as pd

df = pd.DataFrame({
    "hours_studied": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "marks":         [35, 42, 50, 54, 62, 65, 74, 78, 85, 90],
    "hours_gaming":  [6, 5, 6, 4, 5, 3, 4, 2, 3, 2],
})
print(df.corr().round(2))
```

```output
               hours_studied  marks  hours_gaming
hours_studied           1.00   1.00         -0.89
marks                   1.00   1.00         -0.86
hours_gaming           -0.89  -0.86          1.00
```

| Value | Meaning |
| --- | --- |
| near **+1** | rise together (study more, score higher) |
| near **-1** | one rises as the other falls (gaming up, marks down) |
| near **0** | no straight-line relationship |

Rules of thumb: below 0.3 weak, 0.3 to 0.7 moderate, above 0.7 strong. These vary by field.

## r squared

Squaring the correlation tells you the share of the variation that one explains:

```python
r = df["hours_studied"].corr(df["marks"])
print(round(r, 3), round(r ** 2, 3))
```

```output
0.998 0.996
```

## Pearson and Spearman

**Pearson** (the default) measures **straight-line** relationships. **Spearman** measures whether one rises as the other rises, in any steady way, and it is less affected by outliers.

```python
x = np.arange(1, 11)
y = x ** 3                              # always rising, but curved
frame = pd.DataFrame({"x": x, "y": y})
print("pearson :", round(frame["x"].corr(frame["y"]), 3))
print("spearman:", round(frame["x"].corr(frame["y"], method="spearman"), 3))
```

```output
pearson : 0.928
spearman: 1.0
```

## The trap: correlation is not causation

Ice-cream sales and drowning accidents rise and fall together through the year. Does ice cream cause drowning? No. Both rise in **summer**, because hot weather is a hidden **third factor** (a *confounder*).

```python
rng = np.random.default_rng(4)
temperature = rng.uniform(20, 40, size=200)
ice_cream = 5 * temperature + rng.normal(0, 15, size=200)
drownings = 0.4 * temperature + rng.normal(0, 3, size=200)

summer = pd.DataFrame({"temperature": temperature, "ice_cream": ice_cream, "drownings": drownings})
print(summer.corr().round(2))
```

```output
             temperature  ice_cream  drownings
temperature         1.00       0.89       0.59
ice_cream           0.89       1.00       0.52
drownings           0.59       0.52       1.00
```

Ice cream and drownings are clearly correlated, yet both are driven by temperature. If you only looked at those two columns, you could be fooled.

| Possible reasons two things correlate | Example |
| --- | --- |
| A causes B | rain causes wet roads |
| B causes A | people who are ill take more medicine, so medicine "predicts" illness |
| A third factor causes both | summer: ice cream and drowning |
| Pure coincidence | only a few data points |

To show cause you need an **experiment** (randomly give one group the change and compare, as in an A/B test), not just observation.

:::warning
A correlation of 0 does not mean "no relationship". It means no **straight-line** relationship. Plot the data: a perfect U-shape has a correlation near 0.
:::

:::interview
**Interviewers often ask:** "Does correlation imply causation?" No. Give the ice-cream and drowning example, name the confounder, and say that randomised experiments are how you establish cause.
:::
