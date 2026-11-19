---
title: Selecting columns and rows
summary: Pick columns by name, rows by label with loc and by position with iloc.
takeaways:
- df["col"] gives a Series; df[["a", "b"]] gives a DataFrame
- loc selects by label; iloc selects by position
- Both loc and iloc take rows first, then columns
---
## Selecting columns

```python
import pandas as pd

df = pd.DataFrame({
    "name": ["Asha", "Ravi", "Meena", "Kiran", "Divya", "Arun"],
    "city": ["Chennai", "Madurai", "Chennai", "Coimbatore", "Salem", "Chennai"],
    "dept": ["CSE", "ECE", "CSE", "IT", "CSE", "ECE"],
    "marks": [92, 78, 85, 66, 88, 71],
})

print(df["name"])             # one column: a Series
```

```output
0     Asha
1     Ravi
2    Meena
3    Kiran
4    Divya
5     Arun
Name: name, dtype: object
```

```python
print(df[["name", "marks"]])  # several columns: a DataFrame
```

```output
    name  marks
0   Asha     92
1   Ravi     78
2  Meena     85
3  Kiran     66
4  Divya     88
5   Arun     71
```

## loc: select by label

`loc[rows, columns]` uses **labels**: the index values and the column names.

```python
print(df.loc[2])                         # the row labelled 2
print(df.loc[1:3, ["name", "marks"]])    # rows 1 to 3, two columns
```

```output
name       Meena
city     Chennai
dept         CSE
marks         85
Name: 2, dtype: object
    name  marks
1   Ravi     78
2  Meena     85
3  Kiran     66
```

:::warning
With `loc`, a slice such as `1:3` includes **both ends** (rows 1, 2 and 3). This is different from normal Python slices.
:::

## iloc: select by position

`iloc[rows, columns]` uses **positions**, counted from 0, like a Python list.

```python
print(df.iloc[0])               # the first row
print(df.iloc[1:3, 0:2])        # rows 1 and 2, first two columns
print(df.iloc[-1, 3])           # last row, fourth column
```

```output
name        Asha
city     Chennai
dept         CSE
marks         92
Name: 0, dtype: object
    name     city
1   Ravi  Madurai
2  Meena  Chennai
71
```

With `iloc` the end of a slice is **excluded**, as in plain Python.

## Using a column as the index

```python
by_name = df.set_index("name")
print(by_name.loc["Meena", "marks"])
print(by_name.loc[["Asha", "Kiran"], "marks"])
```

```output
85
name
Asha     92
Kiran    66
Name: marks, dtype: int64
```

| You want | Use |
| --- | --- |
| one column | `df["col"]` |
| several columns | `df[["a", "b"]]` |
| a row by label | `df.loc[label]` |
| a row by position | `df.iloc[position]` |
| a cell | `df.loc[label, "col"]` or `df.at[label, "col"]` |

:::tip
If you are not sure which to use, ask: "do I know the **name** of what I want, or its **place**?" Name means `loc`, place means `iloc`.
:::
