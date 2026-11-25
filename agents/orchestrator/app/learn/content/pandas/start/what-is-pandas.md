---
title: What is Pandas?
summary: Pandas is Python's library for working with tables of data. Install it, import it and make your first table.
takeaways:
- Pandas works with tables, like Excel inside Python
- A DataFrame is a table; a Series is one column of it
- Everything in this course uses the import pandas as pd convention
---
## Excel, but with code

Most real data arrives as a table: rows of students, orders, patients or clicks. **Pandas** is the Python library for working with such tables. You can load a million rows, clean them, summarise them and save the result, all in a few lines that you can run again tomorrow.

It is the first tool almost every data analyst and data scientist learns.

| Task | In Excel | In Pandas |
| --- | --- | --- |
| Open a file | double-click | `pd.read_csv("file.csv")` |
| Keep rows that match | filter button | `df[df["marks"] > 80]` |
| Average per group | pivot table | `df.groupby("dept")["marks"].mean()` |
| Remove duplicates | Remove Duplicates | `df.drop_duplicates()` |

## Install and import

```py
pip install pandas
```

In every program, import it with the short name `pd`. Everyone uses this name:

```python
import pandas as pd
print(pd.__version__ >= "2.0")
```

```output
True
```

## Your first DataFrame

A **DataFrame** is a table with named columns. Build one from a dictionary, where each key is a column:

```python
df = pd.DataFrame({
    "name": ["Asha", "Ravi", "Meena", "Kiran", "Divya", "Arun"],
    "city": ["Chennai", "Madurai", "Chennai", "Coimbatore", "Salem", "Chennai"],
    "dept": ["CSE", "ECE", "CSE", "IT", "CSE", "ECE"],
    "marks": [92, 78, 85, 66, 88, 71],
})
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

The numbers on the left (0 to 5) are the **index**: a label for each row. Pandas adds it for you.

## A quick look

```python
print(df.shape)       # (rows, columns)
print(list(df.columns))
print(df["marks"].mean())
```

```output
(6, 4)
['name', 'city', 'dept', 'marks']
80.0
```

:::note
You will use this same small table of students through most of the course. You can copy any code box into a Python file or a notebook and run it.
:::

:::tip
Install Jupyter (`pip install notebook`) or use Google Colab to try Pandas. A notebook shows a DataFrame as a neat table, so you see results straight away.
:::
