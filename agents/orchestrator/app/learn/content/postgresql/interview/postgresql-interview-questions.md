---
title: PostgreSQL interview questions
summary: Common PostgreSQL questions, with short answers you can say in an interview.
takeaways:
- Be ready to explain indexes, transactions, MVCC and JSONB
- Know the difference between WHERE and HAVING, and RANK and DENSE_RANK
- Give a small example with every answer
kind: qa
---
### Q [Easy] What is PostgreSQL and why use it?
An open-source relational database that follows SQL standards, with strong data integrity (ACID), and extras such as JSONB, window functions, full-text search and extensions. It is reliable and free.

### Q [Easy] What is the difference between a primary key and a unique key?
Both prevent duplicates. A table has **one** primary key and it cannot be NULL. A table can have **many** unique constraints.

### Q [Easy] What is a foreign key?
A column that must match a value in another table's key, which keeps relationships valid (an enrollment cannot refer to a student who does not exist).

### Q [Medium] What is an index? When does it hurt?
A sorted structure that speeds up lookups. It slows down inserts and updates and uses disk space, so index only columns used in filters, joins and sorting.

### Q [Medium] How do you find out why a query is slow?
Run `EXPLAIN ANALYZE`. Look for sequential scans on large tables, big gaps between estimated and actual rows, and slow sort or join steps. Add or fix an index, rewrite the query, run `ANALYZE`, then measure again.

### Q [Medium] What are ACID properties?
Atomicity (all or nothing), Consistency (constraints hold), Isolation (concurrent transactions do not interfere), Durability (committed data survives a crash).

### Q [Medium] What is MVCC?
Multi-version concurrency control. Postgres keeps versions of rows so readers do not block writers and writers do not block readers. Old versions are cleaned up by **VACUUM**.

### Q [Medium] JSON vs JSONB?
`JSON` stores the exact text. `JSONB` stores a parsed binary form that is faster to query and can be indexed with GIN. Use JSONB almost always.

### Q [Medium] Difference between WHERE and HAVING?
`WHERE` filters rows before grouping. `HAVING` filters groups after aggregation.

### Q [Medium] What is a CTE?
A named temporary result defined with `WITH`, used to break a complex query into readable steps.

### Q [Hard] Explain isolation levels.
Read Committed (default, each statement sees committed data), Repeatable Read (one snapshot for the whole transaction), Serializable (behaves as if transactions ran one at a time, may need a retry). Higher levels prevent more anomalies but cost more.

### Q [Hard] What causes a deadlock and how do you avoid it?
Two transactions each hold a lock the other needs. Avoid by updating rows in a consistent order, keeping transactions short and locking only what you need. Postgres detects deadlocks and aborts one transaction.

### Q [Hard] How would you find the top 3 students per class?
Use `ROW_NUMBER() OVER (PARTITION BY class ORDER BY marks DESC)` in a subquery and keep rows where the number is 3 or less.

### Q [Hard] How do you prevent SQL injection?
Use parameterised queries (placeholders), never build SQL by joining strings with user input, give the app a limited role and validate input.
