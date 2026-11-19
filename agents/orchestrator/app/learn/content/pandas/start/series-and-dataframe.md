---
title: Series and DataFrame
summary: The two Pandas building blocks: a Series is one labelled column, a DataFrame is a table of Series.
takeaways:
- A Series is a column with an index; a DataFrame is several Series side by side
- You can build a DataFrame from a dict of lists or a list of dicts
- dtypes tells you what kind of data each column holds
---
## Series: one column

A **Series** is a list of values with a label for each one (the index).

```python
import pandas as pd

marks = pd.Series([92, 78, 85], index=["Asha", "Ravi", "Meena"])
print(marks)
print(marks["Ravi"])
```

```output
Asha     92
Ravi     78
Meena    85
dtype: int64
78
```

You can do arithmetic on the whole Series at once. There is no loop:

```python
print(marks + 5)
print(marks.max(), marks.idxmax())
```

```output
Asha     97
Ravi     83
Meena    90
dtype: int64
92 Asha
```

`idxmax()` gives the **label** of the largest value.

## DataFrame: a table of Series

A DataFrame is several Series that share an index. Two common ways to build one:

```python
# 1. A dict of columns
a = pd.DataFrame({"name": ["Asha", "Ravi"], "marks": [92, 78]})

# 2. A list of rows (one dict per row)
b = pd.DataFrame([
    {"name": "Asha", "marks": 92},
    {"name": "Ravi", "marks": 78},
])
print(a.equals(b))
print(a)
```

```output
True
   name  marks
0  Asha     92
1  Ravi     78
```

## Inspecting a DataFrame

```python
df = pd.DataFrame({
    "name": ["Asha", "Ravi", "Meena"],
    "marks": [92, 78, 85],
    "passed": [True, True, True],
})
print(df.shape)
print(df.dtypes)
```

```output
(3, 3)
name      object
marks      int64
passed      bool
dtype: object
```

| Attribute | Meaning |
| --- | --- |
| `df.shape` | (number of rows, number of columns) |
| `df.columns` | the column names |
| `df.index` | the row labels |
| `df.dtypes` | the data type of each column |
| `len(df)` | the number of rows |

`object` means text (strings). `int64` is a whole number, `float64` a decimal number and `bool` true or false.

:::remember
A single column of a DataFrame, `df["marks"]`, is a **Series**. Two or more columns, `df[["name", "marks"]]`, give a DataFrame. Note the double brackets.
:::
