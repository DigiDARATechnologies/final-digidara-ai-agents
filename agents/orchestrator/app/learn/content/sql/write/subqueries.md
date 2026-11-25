---
title: Subqueries
summary: Use the result of one query inside another, in WHERE, FROM and SELECT.
takeaways:
- A subquery is a query inside brackets inside another query
- It often answers questions like above average or not in another table
- Joins are often clearer than subqueries
---
## A query inside a query

Who scored above the average?

```sql
SELECT name, marks
FROM students
WHERE marks > (SELECT AVG(marks) FROM students);
```

The bracketed query runs first and gives one number (80.25 in our table). The outer query then uses it.

| name | marks |
| --- | --- |
| Asha | 92 |
| Meena | 85 |

## A list from a subquery

```sql
SELECT name
FROM students
WHERE id IN (SELECT student_id FROM enrolments WHERE course = 'Python');
```

Gives every student enrolled in Python.

## NOT IN and NOT EXISTS

Students with no enrolment:

```sql
SELECT name
FROM students s
WHERE NOT EXISTS (
  SELECT 1 FROM enrolments e WHERE e.student_id = s.id
);
```

:::warning
`NOT IN` returns nothing if the subquery produces even one `NULL`. `NOT EXISTS` avoids that problem.
:::

## A subquery as a table

```sql
SELECT city, avg_marks
FROM (
  SELECT city, AVG(marks) AS avg_marks
  FROM students
  GROUP BY city
) AS by_city
WHERE avg_marks > 75;
```

The inner query makes a temporary table (`by_city`) that the outer query filters.

## Second highest, with a subquery

```sql
SELECT MAX(marks)
FROM students
WHERE marks < (SELECT MAX(marks) FROM students);
```

:::tip
If a subquery feels confusing, run it **alone** first. Check what it returns, then put it back inside the bigger query.
:::

:::practice mock-interview
Practise talking through a query step by step in a Mock Interview.
:::
