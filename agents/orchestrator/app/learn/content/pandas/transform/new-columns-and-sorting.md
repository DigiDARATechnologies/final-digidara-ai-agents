---
title: New columns and sorting
summary: Add columns from calculations, np.where, apply, map and cut, and sort and rank the results.
takeaways:
- A new column is just an assignment: df["new"] = ...
- np.where and pd.cut turn numbers into labels
- sort_values orders rows; nlargest gives the top few
---
## A column from a calculation

```python
import pandas as pd
import numpy as np

df = pd.DataFrame({
    "name": ["Asha", "Ravi", "Meena", "Kiran", "Divya", "Arun"],
    "dept": ["CSE", "ECE", "CSE", "IT", "CSE", "ECE"],
    "marks": [92, 78, 85, 66, 88, 71],
})
df["percent"] = df["marks"] / 100 * 100
df["bonus"] = df["marks"] + 5
print(df.head(3))
```

```output
    name dept  marks  percent  bonus
0   Asha  CSE     92     92.0     97
1   Ravi  ECE     78     78.0     83
2  Meena  CSE     85     85.0     90
```

The calculation runs on the whole column at once.

## Two-way choices: np.where

```python
df["result"] = np.where(df["marks"] >= 70, "Pass", "Fail")
print(df[["name", "marks", "result"]])
```

```output
    name  marks result
0   Asha     92   Pass
1   Ravi     78   Pass
2  Meena     85   Pass
3  Kiran     66   Fail
4  Divya     88   Pass
5   Arun     71   Pass
```

## Several bands: pd.cut

```python
df["grade"] = pd.cut(df["marks"], bins=[0, 69, 79, 89, 100], labels=["D", "C", "B", "A"])
print(df[["name", "marks", "grade"]])
```

```output
    name  marks grade
0   Asha     92     A
1   Ravi     78     C
2  Meena     85     B
3  Kiran     66     D
4  Divya     88     B
5   Arun     71     C
```

## Your own rule: apply and map

`map` swaps values using a dictionary. `apply` runs a function on each value.

```python
df["dept_name"] = df["dept"].map({"CSE": "Computer Science", "ECE": "Electronics", "IT": "Information Tech"})
df["initial"] = df["name"].apply(lambda n: n[0])
print(df[["name", "dept_name", "initial"]].head(3))
```

```output
    name         dept_name initial
0   Asha  Computer Science       A
1   Ravi       Electronics       R
2  Meena  Computer Science       M
```

:::tip
Prefer built-in column operations (`+`, `str.`, `np.where`) over `apply` when you can. They are much faster on big tables, because `apply` calls Python once per row.
:::

## Sorting

```python
print(df.sort_values("marks", ascending=False)[["name", "marks"]])
```

```output
    name  marks
0   Asha     92
4  Divya     88
2  Meena     85
1   Ravi     78
5   Arun     71
3  Kiran     66
```

Sort by several columns, each in its own direction:

```python
print(df.sort_values(["dept", "marks"], ascending=[True, False])[["dept", "name", "marks"]])
```

```output
  dept   name  marks
0  CSE   Asha     92
4  CSE  Divya     88
2  CSE  Meena     85
1  ECE   Ravi     78
5  ECE   Arun     71
3   IT  Kiran     66
```

## The top few

```python
print(df.nlargest(3, "marks")[["name", "marks"]])
print(df["marks"].rank(ascending=False).astype(int).tolist())
```

```output
    name  marks
0   Asha     92
4  Divya     88
2  Meena     85
[1, 4, 3, 6, 2, 5]
```

`rank` gives each row its position: 1 for the highest mark.
