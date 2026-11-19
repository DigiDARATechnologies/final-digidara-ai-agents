---
title: Filtering rows
summary: Keep only the rows that match a condition, using boolean masks, isin, between, str.contains and query.
takeaways:
- A condition on a column gives a True/False mask; put the mask in df[...]
- Combine conditions with & (and), | (or) and ~ (not), each in brackets
- isin, between and query make common filters shorter
---
## The idea: a mask

A comparison on a column checks **every row at once** and gives True or False for each:

```python
import pandas as pd

df = pd.DataFrame({
    "name": ["Asha", "Ravi", "Meena", "Kiran", "Divya", "Arun"],
    "city": ["Chennai", "Madurai", "Chennai", "Coimbatore", "Salem", "Chennai"],
    "dept": ["CSE", "ECE", "CSE", "IT", "CSE", "ECE"],
    "marks": [92, 78, 85, 66, 88, 71],
})

mask = df["marks"] >= 80
print(mask)
```

```output
0     True
1    False
2     True
3    False
4     True
5    False
Name: marks, dtype: bool
```

Put the mask inside `df[...]` to keep only the True rows:

```python
print(df[df["marks"] >= 80])
```

```output
    name     city dept  marks
0   Asha  Chennai  CSE     92
2  Meena  Chennai  CSE     85
4  Divya    Salem  CSE     88
```

## Combining conditions

Use `&` for and, `|` for or, `~` for not. **Each condition needs its own brackets.**

```python
print(df[(df["dept"] == "CSE") & (df["marks"] > 85)])
print(df[(df["city"] == "Salem") | (df["marks"] < 70)])
print(df[~(df["dept"] == "CSE")])
```

```output
    name     city dept  marks
0   Asha  Chennai  CSE     92
4  Divya    Salem  CSE     88
    name        city dept  marks
3  Kiran  Coimbatore   IT     66
4  Divya       Salem  CSE     88
    name        city dept  marks
1   Ravi     Madurai  ECE     78
3  Kiran  Coimbatore   IT     66
5   Arun     Chennai  ECE     71
```

:::warning
Do not write `and` or `or` here. Python's `and` cannot compare whole columns and raises a `ValueError`. Use `&` and `|` with brackets.
:::

## Shortcuts

```python
print(df[df["city"].isin(["Chennai", "Salem"])])     # one of several values
print(df[df["marks"].between(70, 85)])               # inclusive range
print(df[df["name"].str.startswith("A")])            # text conditions
```

```output
    name     city dept  marks
0   Asha  Chennai  CSE     92
2  Meena  Chennai  CSE     85
4  Divya    Salem  CSE     88
5   Arun  Chennai  ECE     71
    name     city dept  marks
1   Ravi  Madurai  ECE     78
2  Meena  Chennai  CSE     85
5   Arun  Chennai  ECE     71
   name     city dept  marks
0  Asha  Chennai  CSE     92
5  Arun  Chennai  ECE     71
```

## query: filters as a sentence

```python
print(df.query("dept == 'CSE' and marks > 85"))
```

```output
    name     city dept  marks
0   Asha  Chennai  CSE     92
4  Divya    Salem  CSE     88
```

`query` reads more like English. To use a Python variable inside it, put `@` in front: `df.query("marks > @limit")`.

## Counting what matches

A mask of True and False can be summed, because True counts as 1:

```python
print((df["marks"] >= 80).sum())
print((df["marks"] >= 80).mean())
```

```output
3
0.5
```

So 3 students scored 80 or more, and 50% of the class did.

:::tip
To change values for the matching rows, use `loc` with the mask: `df.loc[df["marks"] < 40, "result"] = "Fail"`.
:::
