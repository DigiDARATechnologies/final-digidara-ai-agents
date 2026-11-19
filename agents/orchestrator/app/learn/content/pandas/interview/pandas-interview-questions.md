---
title: Pandas interview questions
summary: The Pandas questions fresher data interviews keep asking, with short answers.
kind: qa
takeaways:
- Be ready to explain Series versus DataFrame and loc versus iloc
- Know how to handle missing data and duplicates
- Practise the groupby and merge answers out loud
---
### Q [Easy] What is Pandas, and what are its two main data structures?
Pandas is a Python library for data analysis. Its two structures are the **Series** (one-dimensional, a labelled column) and the **DataFrame** (two-dimensional, a table of columns that share an index).

### Q [Easy] What is the difference between a Series and a DataFrame?
A Series holds one column of data with an index. A DataFrame is a table made of several Series. Selecting one column of a DataFrame gives a Series.

### Q [Medium] What is the difference between `loc` and `iloc`?
`loc` selects by **label** (index values and column names) and includes both ends of a slice. `iloc` selects by **integer position** and excludes the end of a slice.

### Q [Easy] How do you read a CSV file and look at the first rows?
`df = pd.read_csv("file.csv")`, then `df.head()`. Follow it with `df.info()` and `df.describe()` to understand the data.

### Q [Medium] How do you handle missing values?
First find them with `df.isna().sum()`. Then either **drop** them with `dropna()` (when few rows are affected) or **fill** them with `fillna()`, using the mean or median for numbers and the most common value or a label for categories. Explain *why* you chose that method.

### Q [Medium] How do you filter rows by more than one condition?
Use boolean masks joined with `&` and `|`, with each condition in brackets: `df[(df["dept"] == "CSE") & (df["marks"] > 80)]`. Python's `and` and `or` do not work on columns.

### Q [Medium] How do you remove duplicate rows?
`df.drop_duplicates()`. Use `subset=[...]` to compare only some columns and `keep="first"` or `"last"` to choose which copy stays.

### Q [Medium] What does `groupby` do? Give an example.
It splits the data into groups, applies a function to each, and combines the results. `df.groupby("dept")["marks"].mean()` gives the average mark per department.

### Q [Medium] What is the difference between `merge`, `join` and `concat`?
`merge` joins two DataFrames on column values, like a SQL join (`how` can be inner, left, right or outer). `join` is a shortcut that joins on the **index**. `concat` stacks DataFrames on top of each other (or side by side).

### Q [Medium] What is the difference between `apply`, `map` and `applymap`?
`map` works on a Series and swaps each value using a dictionary or function. `apply` runs a function on each value of a Series, or on each row or column of a DataFrame. For element-wise work on a whole DataFrame, use `df.map(func)` (called `applymap` in older versions).

### Q [Hard] Why is `apply` slower than vectorised operations?
`apply` calls a Python function once per row or value, which is slow in a loop. Vectorised operations such as `df["a"] + df["b"]` run in optimised compiled code on the whole column. Prefer built-in operations and use `apply` only when there is no alternative.

### Q [Hard] What is the `SettingWithCopyWarning`?
It appears when you assign to something that may be a **copy** of a slice, so the original data might not change. Avoid it by selecting and assigning in one step with `loc` (`df.loc[mask, "col"] = value`) or by making an explicit `.copy()`.

### Q [Medium] How would you find the top 3 values in each group?
Sort, then take the first three of each group: `df.sort_values("marks", ascending=False).groupby("dept").head(3)`. Another way is `groupby("dept")["marks"].nlargest(3)`.

:::practice mock-interview
Practise explaining these answers aloud in a Mock Interview.
:::
