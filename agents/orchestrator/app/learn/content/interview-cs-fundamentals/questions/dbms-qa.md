---
title: DBMS questions
summary: Keys, normalization, transactions and ACID, indexing, and joins explained for interviews.
kind: qa
takeaways:
- Know the types of keys and the normal forms 1NF to BCNF
- Explain ACID and isolation problems
- Understand what an index does and costs
---
### Q [Easy] What is a DBMS and why use it over files?
A system to store, retrieve and manage data. It gives data integrity, reduced redundancy, concurrent access, security, backup and a query language, which plain files do not.

### Q [Easy] What are the types of keys?
**Primary key** (unique, not null), **candidate key** (any minimal unique column set), **super key** (any set that is unique), **foreign key** (refers to another table's key), **composite key** (more than one column) and **unique key**.

### Q [Easy] DELETE vs TRUNCATE vs DROP?
`DELETE` removes selected rows (can use `WHERE`, can roll back, logged). `TRUNCATE` removes all rows quickly and resets the table. `DROP` removes the table itself (structure and data).

### Q [Medium] What is normalization? Explain the normal forms.
Organising data to reduce redundancy and anomalies. **1NF**: atomic values, no repeating groups. **2NF**: 1NF plus no partial dependency on part of a composite key. **3NF**: 2NF plus no transitive dependency (non-key depends only on the key). **BCNF**: every determinant is a candidate key.

### Q [Medium] What is denormalization and when do you use it?
Deliberately adding redundancy (joining tables or copying columns) to make reads faster, for example in reporting. It trades storage and update complexity for speed.

### Q [Medium] What are ACID properties?
**Atomicity** (all or nothing), **Consistency** (valid state to valid state), **Isolation** (concurrent transactions do not interfere), **Durability** (committed data survives crashes).

### Q [Medium] What are transaction isolation problems?
**Dirty read** (reading uncommitted data), **non-repeatable read** (the same row changes between reads), **phantom read** (new rows appear between reads). Higher isolation levels prevent more of them.

### Q [Medium] What is an index? Pros and cons?
A structure (usually a B-tree) that speeds up lookups. It makes reads faster but uses space and slows inserts, updates and deletes.

### Q [Medium] Clustered vs non-clustered index?
A **clustered** index decides the physical order of rows (one per table). A **non-clustered** index is a separate structure with pointers to the rows (many per table).

### Q [Medium] What are joins?
Combining rows of two tables: **INNER** (matches only), **LEFT** and **RIGHT OUTER** (keep all of one side), **FULL OUTER** (all of both), **CROSS** (every combination) and **SELF** (a table with itself).

### Q [Medium] WHERE vs HAVING?
`WHERE` filters rows **before** grouping. `HAVING` filters groups **after** aggregation.

### Q [Medium] What is a view?
A saved query that behaves like a virtual table. It simplifies complex queries and can restrict which columns users see.

### Q [Hard] What is a deadlock in a database?
Two transactions each hold a lock the other needs. The DBMS detects it and rolls back one transaction (the victim).

### Q [Hard] SQL vs NoSQL?
SQL databases use tables, a fixed schema, joins and strong ACID guarantees. NoSQL databases (document, key-value, column, graph) have flexible schemas and scale out easily, often trading some consistency for availability and speed.

### Q [Hard] What is the CAP theorem?
In a distributed system you can have only two of **Consistency**, **Availability** and **Partition tolerance**; since network partitions happen, you choose between consistency and availability during a partition.
