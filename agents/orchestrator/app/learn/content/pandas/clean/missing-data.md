---
title: Handling missing data
summary: Find missing values (NaN), remove them with dropna and fill them with fillna.
takeaways:
- Missing values appear as NaN; isna() finds them
- dropna removes rows; fillna replaces the gaps
- Fill numbers with the mean or median, and say why
---
## What missing data looks like

Real data always has gaps. Pandas shows them as **NaN** ("not a number").

```python
import pandas as pd
import numpy as np

df = pd.DataFrame({
    "name": ["Asha", "Ravi", "Meena", "Kiran", "Divya"],
    "marks": [92, np.nan, 85, 66, np.nan],
    "city": ["Chennai", "Madurai", None, "Coimbatore", "Salem"],
})
print(df)
```

```output
    name  marks        city
0   Asha   92.0     Chennai
1   Ravi    NaN     Madurai
2  Meena   85.0        None
3  Kiran   66.0  Coimbatore
4  Divya    NaN       Salem
```

## Finding the gaps

```python
print(df.isna())              # True where a value is missing
print(df.isna().sum())        # missing values per column
print(df["marks"].notna().sum())
```

```output
    name  marks   city
0  False  False  False
1  False   True  False
2  False  False   True
3  False  False  False
4  False   True  False
name     0
marks    2
city     1
dtype: int64
3
```

## Option 1: drop

```python
print(df.dropna())                   # drop any row with a gap
print(df.dropna(subset=["marks"]))   # only if marks is missing
```

```output
    name  marks        city
0   Asha   92.0     Chennai
3  Kiran   66.0  Coimbatore
    name  marks        city
0   Asha   92.0     Chennai
2  Meena   85.0        None
3  Kiran   66.0  Coimbatore
```

Dropping is simple but you lose data. Use it when few rows are affected.

## Option 2: fill

```python
filled = df.copy()
filled["marks"] = filled["marks"].fillna(filled["marks"].mean())
filled["city"] = filled["city"].fillna("Unknown")
print(filled)
```

```output
    name  marks        city
0   Asha   92.0     Chennai
1   Ravi   81.0     Madurai
2  Meena   85.0     Unknown
3  Kiran   66.0  Coimbatore
4  Divya   81.0       Salem
```

| Fill with | When |
| --- | --- |
| the **mean** | numbers with no extreme values |
| the **median** | numbers with outliers (a few very large or small values) |
| the **most common** value (`mode()[0]`) | categories |
| a fixed word such as "Unknown" | text where you want to keep the row |
| the previous value (`ffill()`) | ordered data like daily readings |

## Why the method matters

```python
print(df["marks"].mean(), df["marks"].median())
```

```output
81.0 85.0
```

:::warning
Pandas **skips** NaN when it calculates a mean, so `mean()` above uses only the three real values. After you fill the gaps with the mean, the mean stays the same but the spread shrinks. Always note how you filled values, as it changes your results.
:::

:::remember
`None` and `np.nan` both count as missing. An empty string `""` does **not**, so convert it first: `df.replace("", np.nan)`.
:::
