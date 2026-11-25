---
title: Views, functions and triggers
summary: Reuse logic inside the database with views, materialized views, functions and triggers.
takeaways:
- A view is a saved query; a materialized view stores its result
- Functions and triggers run logic inside the database
- Use them for rules that must hold everywhere, and keep them simple
---
## Views

A **view** is a saved query you can use like a table.

```sql
CREATE VIEW student_summary AS
SELECT s.id, s.name, COUNT(e.id) AS courses
FROM students s
LEFT JOIN enrollments e ON e.student_id = s.id
GROUP BY s.id, s.name;

SELECT * FROM student_summary WHERE courses = 0;
```

Views hide complexity and can limit which columns a user may see.

## Materialized views

A **materialized view** stores the result on disk, so heavy reports are fast. You refresh it when needed.

```sql
CREATE MATERIALIZED VIEW daily_revenue AS
SELECT date_trunc('day', paid_at) AS day, SUM(amount) AS total
FROM payments GROUP BY 1;

REFRESH MATERIALIZED VIEW daily_revenue;
```

## Functions

```sql
CREATE FUNCTION grade(marks INTEGER) RETURNS TEXT AS $$
BEGIN
    IF marks >= 75 THEN RETURN 'Distinction';
    ELSIF marks >= 35 THEN RETURN 'Pass';
    ELSE RETURN 'Fail';
    END IF;
END;
$$ LANGUAGE plpgsql;

SELECT name, grade(marks) FROM students;
```

`plpgsql` is Postgres's procedural language, with variables, `IF` and loops.

## Triggers

A **trigger** runs a function automatically when a row is inserted, updated or deleted. A classic use is keeping an `updated_at` column current.

```sql
CREATE FUNCTION touch_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER students_touch
BEFORE UPDATE ON students
FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
```

`NEW` is the row being written.

## Advice

- Triggers are **invisible** to people reading the app code, so document them and use them sparingly.
- Put business rules in one place. Rules that must hold for every program belong in the database; the rest can stay in your app.
