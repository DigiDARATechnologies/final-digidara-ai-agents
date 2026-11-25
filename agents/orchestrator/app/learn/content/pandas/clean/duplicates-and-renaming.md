---
title: Duplicates, renaming and replacing
summary: Remove duplicate rows, rename and drop columns, and replace values.
takeaways:
- duplicated() finds repeats; drop_duplicates() removes them
- rename changes column names; drop removes columns
- replace changes values, and clip limits extremes
---
## Duplicate rows

```python
import pandas as pd

df = pd.DataFrame({
    "name": ["Asha", "Ravi", "Asha", "Meena", "Ravi"],
    "city": ["Chennai", "Madurai", "Chennai", "Chennai", "Madurai"],
    "marks": [92, 78, 92, 85, 80],
})
print(df.duplicated())
```

```output
0    False
1    False
2     True
3    False
4    False
dtype: bool
```

Row 2 is an exact copy of row 0. Remove it:

```python
print(df.drop_duplicates())
```

```output
    name     city  marks
0   Asha  Chennai     92
1   Ravi  Madurai     78
3  Meena  Chennai     85
4   Ravi  Madurai     80
```

Row 4 stayed because its marks (80) differ from row 1 (78). To decide by some columns only, and keep the last copy:

```python
print(df.drop_duplicates(subset=["name"], keep="last"))
```

```output
    name     city  marks
2   Asha  Chennai     92
3  Meena  Chennai     85
4   Ravi  Madurai     80
```

## Renaming and dropping columns

```python
tidy = df.rename(columns={"marks": "score", "city": "town"})
print(tidy.columns.tolist())

smaller = df.drop(columns=["city"])
print(smaller.columns.tolist())
```

```output
['name', 'town', 'score']
['name', 'marks']
```

Tidy column names early: lowercase with underscores, no spaces, so you can write `df.score` and avoid typing errors.

```python
df.columns = [c.lower().replace(" ", "_") for c in df.columns]
```

## Replacing values

```python
codes = pd.DataFrame({"dept": ["CSE", "ECE", "CSE", "IT"]})
codes["dept_full"] = codes["dept"].replace({"CSE": "Computer Science", "ECE": "Electronics", "IT": "Information Technology"})
print(codes)
```

```output
  dept               dept_full
0  CSE        Computer Science
1  ECE             Electronics
2  CSE        Computer Science
3   IT  Information Technology
```

## Limiting extremes

`clip` pulls values outside a range back to the edges:

```python
marks = pd.Series([35, 60, 105, 88, -5])
print(marks.clip(lower=0, upper=100))
```

```output
0     35
1     60
2    100
3     88
4      0
dtype: int64
```

:::warning
`drop_duplicates()`, `rename()` and `drop()` give you a **new** DataFrame and leave the original alone. Save the result: `df = df.drop_duplicates()`.
:::
