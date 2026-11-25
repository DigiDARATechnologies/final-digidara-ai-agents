---
title: SQL advanced concepts
summary: Indexes, transactions, views, window functions, CTEs, EXISTS versus IN, NULL handling and optimisation.
kind: qa
takeaways:
- Explain indexes, ACID and normalisation briefly and correctly
- Know UNION vs UNION ALL, EXISTS vs IN and how NULL behaves
- Describe how to speed up a slow query
---
### Q [Medium] What is an index and when should you avoid one?
A sorted structure (usually a B-tree) that speeds up searches. It slows `INSERT`, `UPDATE` and `DELETE` and uses space, so avoid indexing columns that are rarely searched, tables that are tiny, or columns with very few distinct values.

### Q [Medium] What is a composite index? Does column order matter?
An index on several columns. Order matters: an index on `(city, age)` helps queries filtering on `city` or on `city` and `age`, but not on `age` alone.

### Q [Medium] Explain ACID.
**Atomicity** (all or nothing), **Consistency** (rules always hold), **Isolation** (transactions do not see each other's half-done work), **Durability** (committed data survives crashes).

### Q [Medium] What is a transaction? Show the commands.
A group of statements treated as one unit.
```sql
BEGIN;
UPDATE accounts SET balance = balance - 500 WHERE id = 1;
UPDATE accounts SET balance = balance + 500 WHERE id = 2;
COMMIT;   -- or ROLLBACK to undo both
```

### Q [Medium] UNION vs UNION ALL?
`UNION` combines results and **removes duplicates** (slower). `UNION ALL` keeps duplicates (faster).

### Q [Medium] IN vs EXISTS?
`IN` compares a value to a list from a subquery. `EXISTS` returns true as soon as a matching row is found, which is often faster for large subqueries. They give the same result for simple cases.

### Q [Medium] How does NULL behave in SQL?
`NULL` means unknown. `NULL = NULL` is not true; use `IS NULL` and `IS NOT NULL`. Aggregates like `AVG` and `COUNT(column)` ignore NULLs, while `COUNT(*)` counts rows. `COALESCE(x, 0)` replaces NULL with a default.

### Q [Medium] What is the difference between `COUNT(*)`, `COUNT(column)` and `COUNT(DISTINCT column)`?
`COUNT(*)` counts all rows. `COUNT(column)` counts rows where the column is not NULL. `COUNT(DISTINCT column)` counts unique non-NULL values.

### Q [Medium] What is a self join? Give a use.
Joining a table to itself, usually with aliases, such as finding each employee's manager from an `employees` table that has a `manager_id`.

### Q [Medium] What is a view and what is a materialized view?
A **view** is a saved query that runs each time it is used. A **materialized view** stores the result physically and must be refreshed, so reads are fast.

### Q [Medium] What is a CTE and why use it?
A named temporary result defined with `WITH`, used to break a complex query into readable steps and to write recursive queries.

### Q [Medium] RANK vs DENSE_RANK vs ROW_NUMBER?
All number rows by an order. `ROW_NUMBER` gives unique numbers (1, 2, 3). `RANK` gives ties the same number and skips after (1, 1, 3). `DENSE_RANK` gives ties the same number without skipping (1, 1, 2).

### Q [Medium] What is a stored procedure and a trigger?
A **stored procedure** is saved SQL code you call by name. A **trigger** runs automatically when a table changes (insert, update, delete), for example to write an audit record.

### Q [Hard] How do you optimise a slow query?
Check the plan with `EXPLAIN`; add **indexes** on filter, join and sort columns; select only needed columns (not `SELECT *`); avoid functions on indexed columns in `WHERE`; filter early; replace correlated subqueries with joins; and consider caching or denormalising for reports.

### Q [Hard] What is the difference between a clustered and a non-clustered index?
A clustered index defines the physical row order (one per table). A non-clustered index is a separate structure pointing to rows (many per table).
