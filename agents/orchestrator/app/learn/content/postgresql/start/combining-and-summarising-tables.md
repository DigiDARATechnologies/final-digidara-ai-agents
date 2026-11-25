---
title: Combining and summarising tables
summary: Combine tables and summarise data with joins, GROUP BY and HAVING, including the FILTER clause.
takeaways:
- JOIN links rows by a matching key; LEFT JOIN keeps unmatched rows
- GROUP BY with COUNT, SUM and AVG summarises groups; HAVING filters groups
- FILTER lets one query count several conditions
---
## Joins

Sample tables: `students(id, name)`, `courses(id, code)`, `enrollments(student_id, course_id)`.

```sql
SELECT s.name, c.code
FROM enrollments e
JOIN students s ON s.id = e.student_id
JOIN courses  c ON c.id = e.course_id
ORDER BY s.name;
```

| Join | Rows returned |
| --- | --- |
| `JOIN` (inner) | only rows that match in both tables |
| `LEFT JOIN` | all rows on the left, with NULLs when nothing matches |
| `FULL JOIN` | all rows from both sides |

**Find students with no enrollment** using a left join:

```sql
SELECT s.name
FROM students s
LEFT JOIN enrollments e ON e.student_id = s.id
WHERE e.id IS NULL;
```

## Aggregates

```sql
SELECT c.code,
       COUNT(*)        AS students,
       ROUND(AVG(s.marks), 1) AS average_marks
FROM enrollments e
JOIN courses  c ON c.id = e.course_id
JOIN students s ON s.id = e.student_id
GROUP BY c.code
HAVING COUNT(*) >= 2
ORDER BY students DESC;
```

- `WHERE` filters **rows before** grouping; `HAVING` filters **groups after**.
- Every column in `SELECT` must be in `GROUP BY` or inside an aggregate.

## FILTER: conditional counts

```sql
SELECT COUNT(*)                         AS total,
       COUNT(*) FILTER (WHERE marks >= 75) AS distinction,
       COUNT(*) FILTER (WHERE marks < 35)  AS failed
FROM students;
```

One pass over the table gives three numbers. It is cleaner than several queries.
