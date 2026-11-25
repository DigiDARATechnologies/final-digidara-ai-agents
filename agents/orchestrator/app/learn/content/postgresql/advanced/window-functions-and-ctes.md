---
title: Window functions and CTEs
summary: Rank rows, compute running totals and write readable multi-step queries with WITH.
takeaways:
- A window function calculates across related rows without collapsing them
- ROW_NUMBER, RANK, LAG and running SUM answer many interview questions
- A CTE (WITH) names a step so complex queries read top to bottom
---
## Window functions

`GROUP BY` collapses rows into one per group. A **window function** keeps every row and adds a calculation next to it, using `OVER (...)`.

Sample table `scores(student, class, marks)`.

```sql
SELECT student, class, marks,
       RANK() OVER (PARTITION BY class ORDER BY marks DESC) AS rank_in_class,
       AVG(marks) OVER (PARTITION BY class)                 AS class_average
FROM scores;
```

- `PARTITION BY class` restarts the calculation for each class.
- `ORDER BY marks DESC` decides the ranking order.

| Function | Gives |
| --- | --- |
| `ROW_NUMBER()` | 1, 2, 3 with no ties |
| `RANK()` | ties share a rank, then a gap (1, 1, 3) |
| `DENSE_RANK()` | ties share a rank, no gap (1, 1, 2) |
| `LAG(x)` / `LEAD(x)` | the previous / next row's value |
| `SUM(x) OVER (ORDER BY d)` | running total |

## Top N per group

```sql
SELECT *
FROM (
    SELECT student, class, marks,
           ROW_NUMBER() OVER (PARTITION BY class ORDER BY marks DESC) AS rn
    FROM scores
) ranked
WHERE rn <= 3;
```

This returns the top 3 students in **each** class, a very common interview question.

## Month-over-month change

```sql
SELECT month, revenue,
       revenue - LAG(revenue) OVER (ORDER BY month) AS change
FROM monthly_sales;
```

## CTEs: name your steps

```sql
WITH class_avg AS (
    SELECT class, AVG(marks) AS avg_marks
    FROM scores
    GROUP BY class
)
SELECT s.student, s.marks, c.avg_marks
FROM scores s
JOIN class_avg c USING (class)
WHERE s.marks > c.avg_marks;
```

The `WITH` part is like a temporary named table. It makes a long query easier to read and test step by step.

## Recursive CTE (idea)

A CTE can refer to itself to walk a hierarchy, such as an employee and their managers up to the top. It is advanced; know that it exists.

:::interview Difference between RANK and DENSE_RANK?
Both give tied rows the same rank. `RANK` skips the next numbers afterwards (1, 1, 3); `DENSE_RANK` does not (1, 1, 2).
:::
