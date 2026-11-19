---
title: Reading data from files
summary: Load a CSV into a DataFrame and inspect it with head, info, describe and value_counts.
takeaways:
- pd.read_csv loads a file; read_excel and read_json work the same way
- head, info and describe are the first three things to run on any new data
- value_counts shows how often each value appears
---
## Loading a CSV

A **CSV** file is plain text with one row per line and commas between the values. It is the most common data format.

For a real file you write `pd.read_csv("students.csv")`. Here the text is built in so you can run the example anywhere:

```python
import pandas as pd
from io import StringIO

csv_text = """name,city,dept,marks
Asha,Chennai,CSE,92
Ravi,Madurai,ECE,78
Meena,Chennai,CSE,85
Kiran,Coimbatore,IT,66
Divya,Salem,CSE,88
Arun,Chennai,ECE,71
"""
df = pd.read_csv(StringIO(csv_text))
print(df)
```

```output
    name        city dept  marks
0   Asha     Chennai  CSE     92
1   Ravi     Madurai  ECE     78
2  Meena     Chennai  CSE     85
3  Kiran  Coimbatore   IT     66
4  Divya       Salem  CSE     88
5   Arun     Chennai  ECE     71
```

Other formats work the same way: `pd.read_excel("file.xlsx")`, `pd.read_json("file.json")`, and `pd.read_sql(query, connection)`.

## The first four commands for any new data

```python
print(df.head(3))     # the first rows (default 5)
print(df.tail(2))     # the last rows
```

```output
    name     city dept  marks
0   Asha  Chennai  CSE     92
1   Ravi  Madurai  ECE     78
2  Meena  Chennai  CSE     85
    name     city dept  marks
4  Divya    Salem  CSE     88
5   Arun  Chennai  ECE     71
```

```python
df.info()
```

```output
<class 'pandas.core.frame.DataFrame'>
RangeIndex: 6 entries, 0 to 5
Data columns (total 4 columns):
 #   Column  Non-Null Count  Dtype
---  ------  --------------  -----
 0   name    6 non-null      object
 1   city    6 non-null      object
 2   dept    6 non-null      object
 3   marks   6 non-null      int64
dtypes: int64(1), object(3)
memory usage: 320.0+ bytes
```

`info()` shows every column, how many values are **not missing**, and its type. It is the quickest way to spot missing data and wrong types.

```python
print(df.describe())
```

```output
           marks
count   6.000000
mean   80.000000
std    10.139033
min    66.000000
25%    72.750000
50%    81.500000
75%    87.250000
max    92.000000
```

`describe()` summarises the **number** columns: count, mean, spread (std), minimum, quartiles and maximum.

## Counting values

```python
print(df["city"].value_counts())
print(df["dept"].nunique())
```

```output
city
Chennai       3
Madurai       1
Coimbatore    1
Salem         1
Name: count, dtype: int64
3
```

## Useful options for read_csv

| Option | What it does |
| --- | --- |
| `sep=";"` | the file uses another separator |
| `usecols=["name", "marks"]` | load only these columns |
| `nrows=1000` | load only the first rows (useful for huge files) |
| `parse_dates=["date"]` | turn a column into dates |
| `na_values=["NA", "-"]` | treat these as missing |

:::tip
Run `head()`, `info()` and `describe()` on every new dataset **before** doing anything else. Most problems (wrong types, missing values, strange numbers) show up in these three outputs.
:::
