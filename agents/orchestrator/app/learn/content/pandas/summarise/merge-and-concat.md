---
title: Merging and combining tables
summary: Join two tables on a shared column with merge, and stack tables with concat.
takeaways:
- merge joins tables on a key, like a SQL join
- how= inner, left, right or outer decides which rows are kept
- concat stacks tables on top of each other (or side by side)
---
## Two tables, one key

Data often lives in separate tables, linked by a shared column.

```python
import pandas as pd

students = pd.DataFrame({
    "student_id": [1, 2, 3, 4],
    "name": ["Asha", "Ravi", "Meena", "Kiran"],
})
scores = pd.DataFrame({
    "student_id": [1, 2, 2, 5],
    "subject": ["Python", "Python", "SQL", "Python"],
    "score": [92, 78, 81, 60],
})
```

## merge

```python
print(students.merge(scores, on="student_id"))
```

```output
   student_id  name subject  score
0           1  Asha  Python     92
1           2  Ravi  Python     78
2           2  Ravi     SQL     81
```

This is an **inner** join: only rows whose `student_id` is in **both** tables. Meena (3) and Kiran (4) have no score, and score row 5 has no matching student, so those rows are dropped. Ravi appears twice because he has two scores.

## Choosing which rows to keep

```python
print(students.merge(scores, on="student_id", how="left"))
```

```output
   student_id   name subject  score
0           1   Asha  Python   92.0
1           2   Ravi  Python   78.0
2           2   Ravi     SQL   81.0
3           3  Meena     NaN    NaN
4           4  Kiran     NaN    NaN
```

| `how=` | Keeps |
| --- | --- |
| `"inner"` (default) | rows with a match in both tables |
| `"left"` | every row of the left table |
| `"right"` | every row of the right table |
| `"outer"` | every row of both |

## Different column names

```python
other = scores.rename(columns={"student_id": "sid"})
print(students.merge(other, left_on="student_id", right_on="sid").shape)
```

```output
(3, 5)
```

## Finding the rows that did not match

```python
check = students.merge(scores, on="student_id", how="left", indicator=True)
print(check[check["_merge"] == "left_only"][["name"]])
```

```output
    name
3  Meena
4  Kiran
```

`indicator=True` adds a column that says where each row came from.

## concat: stacking tables

When two tables have the **same columns** (for example, one file per month), stack them:

```python
jan = pd.DataFrame({"name": ["Asha", "Ravi"], "sales": [100, 120]})
feb = pd.DataFrame({"name": ["Asha", "Ravi"], "sales": [140, 90]})
both = pd.concat([jan, feb], ignore_index=True)
print(both)
```

```output
   name  sales
0  Asha    100
1  Ravi    120
2  Asha    140
3  Ravi     90
```

`ignore_index=True` renumbers the rows 0, 1, 2, 3.

:::warning
Always check the **row count** after a merge. If it grew unexpectedly, the key is repeated in one table (a "one-to-many" join) and you may be counting rows twice.
:::

:::interview
**Interviewers often ask:** "What is the difference between `merge`, `join` and `concat`?" `merge` joins on column values like SQL. `join` is a shortcut that joins on the index. `concat` simply stacks tables along an axis.
:::
