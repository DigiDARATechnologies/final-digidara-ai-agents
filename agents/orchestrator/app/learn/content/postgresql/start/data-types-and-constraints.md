---
title: Data types and constraints
summary: Choose the right column types and use constraints so the database itself refuses bad data.
takeaways:
- Pick precise types: TEXT, INTEGER, NUMERIC, BOOLEAN, DATE, TIMESTAMPTZ
- Use NUMERIC for money, never floating point
- PRIMARY KEY, FOREIGN KEY, UNIQUE, NOT NULL and CHECK protect your data
---
## Common types

| Type | Use for | Example |
| --- | --- | --- |
| `INTEGER`, `BIGINT` | whole numbers | `42` |
| `NUMERIC(10,2)` | exact decimals such as money | `1999.50` |
| `TEXT`, `VARCHAR(n)` | text | `'Asha'` |
| `BOOLEAN` | true or false | `TRUE` |
| `DATE` | a date | `'2026-03-12'` |
| `TIMESTAMPTZ` | date and time **with time zone** | `'2026-03-12 10:30+05:30'` |
| `UUID` | unique identifiers | generated ids |
| `JSONB` | JSON data (later lesson) | `'{"a":1}'` |

Use **`NUMERIC` for money**: `FLOAT` stores approximations and can give `0.1 + 0.2 = 0.30000000000000004`. Prefer `TIMESTAMPTZ` over `TIMESTAMP` so times are not confused across time zones. In Postgres `TEXT` and `VARCHAR` perform the same, so use `TEXT` unless you need a length limit.

## Constraints: rules the database enforces

```sql
CREATE TABLE courses (
    id    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code  TEXT NOT NULL UNIQUE,
    fee   NUMERIC(10,2) NOT NULL CHECK (fee >= 0)
);

CREATE TABLE enrollments (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id  INTEGER NOT NULL REFERENCES courses(id),
    enrolled   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (student_id, course_id)
);
```

| Constraint | Meaning |
| --- | --- |
| `PRIMARY KEY` | unique, not null row identifier |
| `NOT NULL` | value required |
| `UNIQUE` | no duplicates (the pair above stops enrolling twice) |
| `CHECK` | custom rule, such as `fee >= 0` |
| `REFERENCES` (foreign key) | must match a row in another table |
| `DEFAULT` | value used when none is given |

`ON DELETE CASCADE` deletes the child rows automatically when the parent is deleted. Use it carefully.

`GENERATED ... AS IDENTITY` is the modern, standard replacement for `SERIAL`.

## Change a table later

```sql
ALTER TABLE students ADD COLUMN email TEXT;
ALTER TABLE students ALTER COLUMN marks SET DEFAULT 0;
ALTER TABLE students DROP COLUMN email;
```

:::remember
Put rules in the database, not only in your app. Then every program that uses it is protected from bad data.
:::
