---
title: Group by and pivot tables
summary: Summarise data per group with groupby, aggregate several ways at once, and build pivot tables and cross-tabs.
takeaways:
- groupby splits the rows into groups, then you summarise each group
- agg lets you ask for several statistics at once
- pivot_table is groupby with the groups spread across rows and columns
---
## Split, apply, combine

"What is the average mark **per department**?" is a groupby question. Pandas splits the rows into groups, calculates for each group, then combines the answers.

```python
import pandas as pd

df = pd.DataFrame({
    "name": ["Asha", "Ravi", "Meena", "Kiran", "Divya", "Arun"],
    "city": ["Chennai", "Madurai", "Chennai", "Coimbatore", "Salem", "Chennai"],
    "dept": ["CSE", "ECE", "CSE", "IT", "CSE", "ECE"],
    "marks": [92, 78, 85, 66, 88, 71],
})
print(df.groupby("dept")["marks"].mean())
```

```output
dept
CSE    88.333333
ECE    74.500000
IT     66.000000
Name: marks, dtype: float64
```

## Several statistics at once

```python
print(df.groupby("dept")["marks"].agg(["count", "mean", "max"]))
```

```output
      count       mean  max
dept
CSE       3  88.333333   92
ECE       2  74.500000   78
IT        1  66.000000   66
```

Give the results your own names with **named aggregation**:

```python
summary = df.groupby("dept").agg(
    students=("name", "count"),
    average=("marks", "mean"),
    best=("marks", "max"),
)
print(summary.round(1))
```

```output
      students  average  best
dept
CSE          3     88.3    92
ECE          2     74.5    78
IT           1     66.0    66
```

## Turning the groups back into columns

The group names become the index. Use `reset_index()` to make them a normal column again:

```python
print(summary.reset_index())
```

```output
  dept  students    average  best
0  CSE         3  88.333333    92
1  ECE         2  74.500000    78
2   IT         1  66.000000    66
```

## Grouping by two columns

```python
print(df.groupby(["dept", "city"])["marks"].mean())
```

```output
dept  city
CSE   Chennai       88.5
      Salem         88.0
ECE   Chennai       71.0
      Madurai       78.0
IT    Coimbatore    66.0
Name: marks, dtype: float64
```

## Counting rows per group

```python
print(df.groupby("city").size().sort_values(ascending=False))
```

```output
city
Chennai       3
Coimbatore    1
Madurai       1
Salem         1
dtype: int64
```

## Pivot tables

`pivot_table` spreads one grouping across the rows and another across the columns, like an Excel pivot:

```python
print(df.pivot_table(index="dept", columns="city", values="marks", aggfunc="mean"))
```

```output
city  Chennai  Coimbatore  Madurai  Salem
dept
CSE      88.5         NaN      NaN   88.0
ECE      71.0         NaN     78.0    NaN
IT        NaN        66.0      NaN    NaN
```

The empty cells are NaN, because no student belongs to that pair. Add `fill_value=0` to show 0 instead.

`pd.crosstab` counts how many rows fall in each pair:

```python
print(pd.crosstab(df["dept"], df["city"]))
```

```output
city  Chennai  Coimbatore  Madurai  Salem
dept
CSE         2           0        0      1
ECE         1           0        1      0
IT          0           1        0      0
```

:::remember
`groupby` ignores missing group labels and returns the groups sorted by name. For the most common questions: **mean per group, count per group, top per group**. These three cover most reports.
:::
