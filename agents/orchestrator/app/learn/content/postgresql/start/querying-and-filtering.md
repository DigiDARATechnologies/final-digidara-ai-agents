---
title: Querying, filtering and RETURNING
summary: Read and change data with Postgres features: ILIKE, LIMIT, ranges, upserts and RETURNING.
takeaways:
- ILIKE matches text without caring about case
- INSERT ... ON CONFLICT is an upsert; RETURNING gives back the changed rows
- LIMIT and OFFSET page through results
---
## Filtering

```sql
SELECT name, marks
FROM students
WHERE marks BETWEEN 60 AND 90
  AND name ILIKE 'a%'
ORDER BY marks DESC
LIMIT 5;
```

- `ILIKE` is a **case-insensitive** `LIKE` (a Postgres feature). `%` means any characters.
- `IN ('a','b')`, `IS NULL`, `BETWEEN`, `AND`, `OR` work as in standard SQL.
- Page through results with `LIMIT 10 OFFSET 20`.

## RETURNING: see what changed

Normally an insert only says "1 row". Add **RETURNING** to get the data back, for example the new id.

```sql
INSERT INTO students (name, marks) VALUES ('Meena', 91) RETURNING id, name;
```

```output
 id | name
----+-------
  3 | Meena
(1 row)
```

It also works for `UPDATE` and `DELETE`, which is handy in applications.

## Upsert: insert or update

```sql
INSERT INTO courses (code, fee)
VALUES ('PY101', 4500)
ON CONFLICT (code) DO UPDATE SET fee = EXCLUDED.fee;
```

If the code already exists, the fee is updated instead of an error. `EXCLUDED` means "the row I tried to insert". Use `DO NOTHING` to just ignore duplicates.

## Update and delete

```sql
UPDATE students SET marks = marks + 5 WHERE name = 'Ravi' RETURNING *;
DELETE FROM students WHERE marks < 35 RETURNING id;
```

:::warning
`UPDATE` or `DELETE` without `WHERE` changes **every row**. In psql run `BEGIN;` first so you can `ROLLBACK;` if the result looks wrong.
:::
