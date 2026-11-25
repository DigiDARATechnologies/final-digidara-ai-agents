---
title: Indexes and EXPLAIN
summary: Make queries fast: how indexes work, how to create them, and how to read EXPLAIN to see what Postgres does.
takeaways:
- An index is a sorted lookup structure that avoids scanning the whole table
- EXPLAIN ANALYZE shows the real plan and time of a query
- Index the columns you filter, join and sort on, but not everything
---
## Why indexes

Without an index, finding one student among a million means reading **every row** (a *sequential scan*). An **index** is like the index at the back of a book: it jumps straight to the right place.

```sql
CREATE INDEX idx_students_email ON students (email);
CREATE UNIQUE INDEX idx_courses_code ON courses (code);
CREATE INDEX idx_enroll_student ON enrollments (student_id, course_id);
```

Primary keys and UNIQUE constraints already create an index automatically. **Foreign key columns are not indexed automatically**, so add indexes on them if you join or delete by them often.

## Read the plan with EXPLAIN

```sql
EXPLAIN ANALYZE
SELECT * FROM students WHERE email = 'asha@example.com';
```

Without an index you see something like `Seq Scan on students` (slow on big tables). With the index you see `Index Scan using idx_students_email` and a much smaller time. The words to look for:

| Plan step | Meaning |
| --- | --- |
| **Seq Scan** | reads the whole table |
| **Index Scan** | uses an index |
| **Bitmap Heap Scan** | index finds many rows, then reads them in batches |
| **cost / actual time** | estimated work / real time in milliseconds |

## Types and special indexes

| Index | Use |
| --- | --- |
| **B-tree** (default) | equality, ranges, sorting |
| **GIN** | JSONB, arrays, full-text search |
| **Partial** | index only some rows: `CREATE INDEX ... WHERE active` |
| **Composite** | several columns; the order matters, leftmost columns first |

## Rules of thumb

- Index columns used in `WHERE`, `JOIN` and `ORDER BY`.
- Every index **slows inserts and updates** and uses disk, so do not add them blindly.
- Wrapping a column in a function (`WHERE lower(email) = ...`) skips a normal index. Create an **expression index** on `lower(email)` instead.
- Run `ANALYZE` (or rely on autovacuum) so Postgres has fresh statistics.

:::tip
Always measure with `EXPLAIN ANALYZE` before and after adding an index. If the plan does not change, drop the index.
:::
