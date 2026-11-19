---
title: Cleaning data and finding outliers
summary: Handle missing values, duplicates and outliers, with the IQR rule and z-scores, and decide what to do with them.
takeaways:
- Clean in a repeatable order: duplicates, types, missing values, outliers
- An outlier is a value far from the rest; it may be an error or a real extreme
- The IQR rule and z-scores find outliers; the decision is yours
---
## A messy dataset

Real data arrives with problems:

```python
import numpy as np
import pandas as pd

raw = pd.DataFrame({
    "name": ["Asha", "Ravi", "Meena", "Kiran", "Divya", "Arun", "Asha", "Latha"],
    "age": [24, 29, np.nan, 31, 27, 30, 24, 26],
    "salary": [32000, 41000, 38000, 45000, 36000, 950000, 32000, 40000],
    "city": ["Chennai", "madurai", "Chennai ", "Salem", "CHENNAI", "Madurai", "Chennai", "Salem"],
})
print(raw)
```

```output
    name   age  salary      city
0   Asha  24.0   32000   Chennai
1   Ravi  29.0   41000   madurai
2  Meena   NaN   38000  Chennai
3  Kiran  31.0   45000     Salem
4  Divya  27.0   36000   CHENNAI
5   Arun  30.0  950000   Madurai
6   Asha  24.0   32000   Chennai
7  Latha  26.0   40000     Salem
```

You can already see four problems: a duplicate row (Asha), a missing age, inconsistent city spelling, and one huge salary.

## Step by step

```python
df = raw.drop_duplicates().copy()                       # 1. duplicates
df["city"] = df["city"].str.strip().str.title()          # 2. consistent text
df["age"] = df["age"].fillna(df["age"].median())         # 3. missing values
print(df)
print(df["city"].value_counts())
```

```output
    name   age  salary     city
0   Asha  24.0   32000  Chennai
1   Ravi  29.0   41000  Madurai
2  Meena  28.0   38000  Chennai
3  Kiran  31.0   45000    Salem
4  Divya  27.0   36000  Chennai
5   Arun  30.0  950000  Madurai
7  Latha  26.0   40000    Salem
city
Chennai    3
Madurai    2
Salem      2
Name: count, dtype: int64
```

## Outliers

An **outlier** is a value far away from the others. It may be a mistake (a typing error), or a real but rare case. The giant salary above could be a typo (950000 instead of 95000) or a real executive. Find them first, then decide.

**Method 1: the IQR rule.** Compute the range of the middle 50% of values (the interquartile range). Anything more than 1.5 times that range beyond the quartiles is flagged:

```python
q1, q3 = df["salary"].quantile([0.25, 0.75])
iqr = q3 - q1
low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
print(f"fences: {low:.0f} to {high:.0f}")
print(df[(df["salary"] < low) | (df["salary"] > high)])
```

```output
fences: 28000 to 52000
   name   age  salary     city
5  Arun  30.0  950000  Madurai
```

**Method 2: the z-score.** How many standard deviations a value is from the mean. A common rule flags values beyond 3 (with small data, a lower cut-off such as 2 is used):

```python
z = (df["salary"] - df["salary"].mean()) / df["salary"].std()
print(z.round(2).tolist())
```

```output
[-0.4, -0.37, -0.38, -0.36, -0.39, 2.27, -0.37]
```

## What to do with an outlier

| If the value is... | Then |
| --- | --- |
| an obvious error (age 250) | fix it from the source, or remove it |
| real but extreme | keep it, but use the **median** and robust methods |
| real and it would distort a model | cap it (winsorise), or transform it (log) |
| unknown | investigate before deciding; ask whoever produced the data |

```python
capped = df["salary"].clip(upper=high)
print("mean before:", round(df["salary"].mean()), " after capping:", round(capped.mean()))
print("median before:", df["salary"].median(), " after capping:", capped.median())
```

```output
mean before: 168857  after capping: 40571
median before: 40000.0  after capping: 40000.0
```

The **mean** moved a lot, but the **median** did not move. That is why the median is a better summary when outliers are present.

:::warning
Never delete outliers just because they are inconvenient. Removing real extremes can hide the very thing you are trying to learn, such as the fraud case or the rare disease.
:::

:::interview
**Interviewers often ask:** "How do you handle outliers?" First detect them (box plot, IQR, z-score). Then find out whether they are errors or real. Fix or remove errors, and for real values choose robust statistics, caps or transformations, and document the decision.
:::
