---
title: SQL basics
summary: Keys, DELETE versus TRUNCATE versus DROP, WHERE versus HAVING, normalisation, UNION and ACID.
kind: qa
takeaways:
- Know primary and foreign keys and the main constraints
- Be able to separate WHERE from HAVING and DELETE from DROP
- ACID and normalisation come up often
---
### Q [Easy] What is the difference between SQL and MySQL?
SQL is the **language** used to work with relational databases. MySQL is a **database system** (software) that understands SQL. Others include PostgreSQL, SQL Server and Oracle.

### Q [Easy] What are primary and foreign keys?
A **primary key** uniquely identifies each row in a table; it cannot be null and there is one per table. A **foreign key** is a column that holds the primary key of another table, linking the two and enforcing that the other row exists.

### Q [Easy] What is the difference between DELETE, TRUNCATE and DROP?
`DELETE` removes chosen rows (with `WHERE`) and can be rolled back. `TRUNCATE` removes **all** rows quickly and keeps the table structure. `DROP` removes the whole table, structure and data.

### Q [Medium] What is the difference between WHERE and HAVING?
`WHERE` filters **rows** before grouping. `HAVING` filters **groups** after `GROUP BY`, so it can use aggregates such as `COUNT(*) > 5`.

### Q [Easy] What is NULL?
`NULL` means unknown or missing. It is not zero or an empty string. Any comparison with `NULL` is unknown, so use `IS NULL` and `IS NOT NULL`.

### Q [Medium] What is the difference between UNION and UNION ALL?
`UNION` combines the results of two queries and **removes duplicates**. `UNION ALL` keeps them, and is faster because it skips that step.

### Q [Medium] What is normalisation?
Organising tables to reduce repeated data. **1NF:** each cell holds one value. **2NF:** every non-key column depends on the whole key. **3NF:** non-key columns depend only on the key, not on each other. It avoids update and delete anomalies.

### Q [Medium] What is an index?
A data structure (usually a B-tree) that makes searching a column fast. The cost: it takes space and slows down inserts and updates, so index the columns you search and join on.

### Q [Hard] What are the ACID properties?
**Atomicity:** a transaction fully happens or not at all. **Consistency:** it moves the database from one valid state to another. **Isolation:** transactions running at once do not disturb each other. **Durability:** once committed, the data survives a crash.

### Q [Easy] What is the difference between CHAR and VARCHAR?
`CHAR(n)` is fixed length and pads with spaces. `VARCHAR(n)` is variable length and uses only what it needs. Use `CHAR` for fixed codes like country codes and `VARCHAR` for names.

:::practice mock-interview
Practise saying these answers in a Mock Interview.
:::
