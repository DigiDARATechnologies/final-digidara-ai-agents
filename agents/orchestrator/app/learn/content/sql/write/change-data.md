---
title: Inserting, updating and deleting
summary: Add rows with INSERT, change them with UPDATE and remove them with DELETE, safely.
takeaways:
- INSERT adds a row; UPDATE changes rows; DELETE removes rows
- Always put a WHERE on UPDATE and DELETE
- Run the SELECT first to check which rows you will touch
---
## INSERT

```sql
INSERT INTO students (name, city, marks)
VALUES ('Divya', 'Salem', 88);
```

List the columns, then the values in the same order. Several rows at once:

```sql
INSERT INTO students (name, city, marks) VALUES
  ('Arun', 'Trichy', 71),
  ('Lakshmi', 'Chennai', 94);
```

## UPDATE

```sql
UPDATE students
SET marks = 90
WHERE name = 'Ravi';
```

Change several columns by separating them with commas:

```sql
UPDATE students
SET city = 'Chennai', marks = marks + 5
WHERE id = 4;
```

## DELETE

```sql
DELETE FROM students
WHERE id = 4;
```

:::warning
`UPDATE` or `DELETE` **without a WHERE** changes or removes every row in the table. There is no undo. Always write the `WHERE` first.
:::

## A safe habit

Before changing rows, run the same condition as a `SELECT`:

```sql
SELECT * FROM students WHERE id = 4;
```

If it shows exactly the rows you expect, change `SELECT *` to `DELETE` and keep the same `WHERE`.

## Transactions

When several changes must succeed together, group them:

```sql
START TRANSACTION;
UPDATE accounts SET balance = balance - 500 WHERE id = 1;
UPDATE accounts SET balance = balance + 500 WHERE id = 2;
COMMIT;
```

If something fails, `ROLLBACK` undoes everything since `START TRANSACTION`. Either both changes happen or neither does.

:::interview
**Interviewers often ask:** "What is the difference between DELETE, TRUNCATE and DROP?" `DELETE` removes chosen rows and can be rolled back. `TRUNCATE` empties the whole table quickly. `DROP` removes the table itself.
:::
