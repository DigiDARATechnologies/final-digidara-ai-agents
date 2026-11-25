---
title: MongoDB interview questions
summary: Common MongoDB questions with short answers: documents, schema design, indexes, aggregation and scaling.
takeaways:
- Explain documents, collections and when MongoDB suits a problem
- Know embed versus reference, indexes and the aggregation pipeline
- Be able to compare MongoDB with SQL fairly
kind: qa
---
### Q [Easy] What is MongoDB?
An open-source **document database** that stores data as flexible JSON-like (BSON) documents in collections, instead of rows in tables.

### Q [Easy] What is the difference between a collection and a table?
A table has a fixed set of columns. A collection holds documents that can have different fields, although you can add validation rules.

### Q [Easy] What is `_id`?
The unique identifier of every document, added automatically as an `ObjectId` if you do not provide one. It is indexed.

### Q [Easy] What is BSON?
Binary JSON: the format MongoDB uses to store documents. It supports extra types such as dates, ObjectId and binary data, and is faster to scan than text JSON.

### Q [Medium] SQL vs MongoDB: when do you choose which?
Choose SQL for strongly related data, strict rules and complex joins and reporting. Choose MongoDB for flexible or nested data read together, fast-changing structure and easy horizontal scaling. Many systems use both.

### Q [Medium] Embed or reference?
Embed data that is read together, owned by the parent and bounded in size. Reference data that is shared, large or can grow without limit. Design around the queries.

### Q [Medium] What is an index and what is a compound index?
An index is a sorted structure that avoids scanning every document. A compound index covers several fields in a given order; follow equality, sort, range when designing it.

### Q [Medium] How do you check whether a query uses an index?
Use `explain("executionStats")` and look for `IXSCAN` instead of `COLLSCAN`, and compare `totalDocsExamined` with `nReturned`.

### Q [Medium] What is the aggregation pipeline?
Stages such as `$match`, `$group`, `$sort`, `$project` and `$lookup` that transform documents one after another. Put `$match` early for speed.

### Q [Medium] `$set` vs replacing a document?
`updateOne` with `$set` changes only the named fields. Passing a plain document to `replaceOne` replaces the entire document.

### Q [Hard] Does MongoDB support transactions?
Yes. Single-document writes are atomic. Multi-document ACID transactions are supported on replica sets, but they are slower, so good schema design avoids needing them.

### Q [Hard] What is a replica set?
A group of MongoDB servers with the same data: one primary for writes and secondaries that copy it. If the primary fails, an election chooses a new one automatically, giving high availability.

### Q [Hard] What is sharding and what makes a good shard key?
Splitting data across servers to scale. A good shard key has high variety, spreads writes evenly and appears in common queries. A steadily increasing key sends all writes to one shard.

### Q [Hard] How can you avoid NoSQL injection?
Never pass raw user JSON into a query. Validate types (force strings), build filters yourself, and block operator keys such as `$ne` and `$gt` in user input.
