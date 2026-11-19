---
title: Joins: combining tables
summary: Link rows from two tables with INNER, LEFT and RIGHT joins.
takeaways:
- Data is split across tables; a join puts it back together
- INNER JOIN keeps only rows that match on both sides
- LEFT JOIN keeps every row from the left table
---
## Why data lives in several tables

Storing a course name again on every enrolment wastes space and invites typos. Instead you keep tables apart and **link** them with a key.

`students`:

| id | name |
| --- | --- |
| 1 | Asha |
| 2 | Ravi |
| 3 | Meena |

`enrolments`:

| student_id | course |
| --- | --- |
| 1 | Python |
| 1 | SQL |
| 2 | Python |

`student_id` is a **foreign key**: it points at `students.id`.

## INNER JOIN

```sql
SELECT students.name, enrolments.course
FROM students
INNER JOIN enrolments ON enrolments.student_id = students.id;
```

| name | course |
| --- | --- |
| Asha | Python |
| Asha | SQL |
| Ravi | Python |

`ON` says how the rows match. Meena has no enrolment, so she is missing.

## LEFT JOIN

```sql
SELECT students.name, enrolments.course
FROM students
LEFT JOIN enrolments ON enrolments.student_id = students.id;
```

| name | course |
| --- | --- |
| Asha | Python |
| Asha | SQL |
| Ravi | Python |
| Meena | NULL |

A `LEFT JOIN` keeps **every** row from the left table. Where there is no match, the right side is `NULL`.

## Finding what is missing

```sql
SELECT students.name
FROM students
LEFT JOIN enrolments ON enrolments.student_id = students.id
WHERE enrolments.student_id IS NULL;
```

Gives the students with no enrolment: Meena.

## Join types at a glance

| Join | Rows returned |
| --- | --- |
| `INNER JOIN` | only matches |
| `LEFT JOIN` | all left rows, matches from the right |
| `RIGHT JOIN` | all right rows, matches from the left |
| `FULL JOIN` | everything from both (not in MySQL) |

## Shorter names

```sql
SELECT s.name, e.course
FROM students s
JOIN enrolments e ON e.student_id = s.id;
```

`JOIN` alone means `INNER JOIN`.

:::interview
**Interviewers often ask:** "Explain INNER versus LEFT JOIN." Inner returns only rows that match in both tables. Left returns all rows from the left table, with `NULL` where the right has no match. Draw the two small tables above to show it.
:::
