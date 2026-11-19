---
title: Exploring a dataset
summary: Do exploratory data analysis (EDA): look at the size, types, summary numbers, groups and relationships before modelling.
takeaways:
- EDA means getting to know your data before you model it
- Check shape, types, missing values and summary statistics first
- Compare groups and look for relationships between columns
---
## Look before you leap

**Exploratory data analysis (EDA)** is what you do before any model: get to know the data. It finds errors, shows what is normal, and suggests which questions are worth asking.

```python
import pandas as pd
from sklearn.datasets import load_wine

wine = load_wine(as_frame=True).frame
cols = ["alcohol", "malic_acid", "color_intensity", "proline", "target"]
df = wine[cols]
print(df.shape)
print(df.head(4))
```

```output
(178, 5)
   alcohol  malic_acid  color_intensity  proline  target
0    14.23        1.71             5.64   1065.0       0
1    13.20        1.78             4.38   1050.0       0
2    13.16        2.36             5.68   1185.0       0
3    14.37        1.95             7.80   1480.0       0
```

## 1. Size, types and gaps

```python
df.info()
```

```output
<class 'pandas.core.frame.DataFrame'>
RangeIndex: 178 entries, 0 to 177
Data columns (total 5 columns):
 #   Column           Non-Null Count  Dtype
---  ------           --------------  -----
 0   alcohol          178 non-null    float64
 1   malic_acid       178 non-null    float64
 2   color_intensity  178 non-null    float64
 3   proline          178 non-null    float64
 4   target           178 non-null    int32
dtypes: float64(4), int32(1)
memory usage: 6.4 KB
```

Check: how many rows and columns, whether the types are right, and whether anything is missing. Here there are no missing values, so no cleaning is needed on this dataset.

## 2. Summary numbers

```python
print(df.describe().round(2))
```

```output
       alcohol  malic_acid  color_intensity  proline  target
count   178.00      178.00           178.00   178.00  178.00
mean     13.00        2.34             5.06   746.89    0.94
std       0.81        1.12             2.32   314.91    0.78
min      11.03        0.74             1.28   278.00    0.00
25%      12.36        1.60             3.22   500.50    0.00
50%      13.05        1.87             4.69   673.50    1.00
75%      13.68        3.08             6.20   985.00    2.00
max      14.83        5.80            13.00  1680.00    2.00
```

Read this table slowly. For each column, compare the **mean** with the **median** (the 50% row), and look at the min and max. Is anything impossible? Is the spread huge? Here `proline` is in the hundreds while `malic_acid` is a few units: very different scales.

## 3. How balanced are the categories?

```python
print(df["target"].value_counts().sort_index())
print(df["target"].value_counts(normalize=True).round(2).sort_index())
```

```output
target
0    59
1    71
2    48
Name: count, dtype: int64
target
0    0.33
1    0.40
2    0.27
Name: proportion, dtype: float64
```

If one class had 95% of the rows, a model could look accurate by always guessing it. Always check the balance.

## 4. Compare groups

```python
print(df.groupby("target").mean().round(2))
```

```output
        alcohol  malic_acid  color_intensity  proline
target
0         13.74        2.01             5.53  1115.71
1         12.28        1.93             3.09   519.51
2         13.15        3.33             7.40   629.90
```

Which columns differ most between the three types? Those are the likely clues for telling them apart.

## 5. Relationships between columns

```python
print(df.corr().round(2))
```

```output
                 alcohol  malic_acid  color_intensity  proline  target
alcohol             1.00        0.09             0.55     0.64   -0.33
malic_acid          0.09        1.00             0.25    -0.19    0.44
color_intensity     0.55        0.25             1.00     0.32    0.27
proline             0.64       -0.19             0.32     1.00   -0.63
target             -0.33        0.44             0.27    -0.63    1.00
```

The table shows the **correlation** of every pair, from -1 to 1. Numbers near 0 mean no straight-line relationship. Numbers near 1 or -1 mean the columns move together.

## An EDA checklist

| Question | Command |
| --- | --- |
| How big is it? | `df.shape` |
| What types are the columns? | `df.info()` |
| Is anything missing? | `df.isna().sum()` |
| What are typical values? | `df.describe()` |
| Are classes balanced? | `df[col].value_counts()` |
| How do groups differ? | `df.groupby(col).mean()` |
| What moves together? | `df.corr()` |
| Anything strange? | charts: histogram, box plot |

:::remember
EDA is where you notice things you did not expect: a column that is mostly zeros, an age of 250, two columns that are the same. Finding these now saves you from a model built on bad data.
:::
