---
title: Sorting, limits and grouping
summary: Order results, limit them, count and total with aggregate functions, and group with GROUP BY.
takeaways:
- ORDER BY sorts; LIMIT keeps the first few rows
- COUNT, SUM, AVG, MIN and MAX summarise many rows into one
- GROUP BY makes one result per group; HAVING filters the groups
---
## Sorting

```sql
SELECT name, marks FROM students ORDER BY marks DESC;
```

| name | marks |
| --- | --- |
| Asha | 92 |
| Meena | 85 |
| Ravi | 78 |
| Kiran | 66 |

`ASC` (low to high) is the default; `DESC` is high to low.

## Limiting

```sql
SELECT name, marks FROM students ORDER BY marks DESC LIMIT 3;
```

Gives the top three. (SQL Server writes `SELECT TOP 3 ...` instead.)

## Removing duplicates

```sql
SELECT DISTINCT city FROM students;
```

## Aggregate functions

An aggregate turns many rows into one value:

```sql
SELECT COUNT(*) AS students, AVG(marks) AS average, MAX(marks) AS best
FROM students;
```

| students | average | best |
| --- | --- | --- |
| 4 | 80.25 | 92 |

`AS` gives the result column a readable name. The functions are `COUNT`, `SUM`, `AVG`, `MIN` and `MAX`.

## GROUP BY

To get a summary **per group**:

```sql
SELECT city, COUNT(*) AS students, AVG(marks) AS average
FROM students
GROUP BY city;
```

| city | students | average |
| --- | --- | --- |
| Chennai | 2 | 88.5 |
| Madurai | 1 | 78 |
| Coimbatore | 1 | 66 |

## HAVING

`WHERE` filters rows. To filter **groups**, use `HAVING`:

```sql
SELECT city, AVG(marks) AS average
FROM students
GROUP BY city
HAVING AVG(marks) > 70;
```

## The order you write and the order SQL thinks

| Written | Meaning |
| --- | --- |
| `SELECT` | what to show |
| `FROM` | which table |
| `WHERE` | filter rows |
| `GROUP BY` | make groups |
| `HAVING` | filter groups |
| `ORDER BY` | sort |
| `LIMIT` | cut |

:::interview
**Interviewers often ask:** "Find the second highest mark." `SELECT DISTINCT marks FROM students ORDER BY marks DESC LIMIT 1 OFFSET 1;` is a common answer.
:::

:::practice mock-interview
SQL questions are a staple of fresher interviews. Rehearse them in a Mock Interview.
:::
