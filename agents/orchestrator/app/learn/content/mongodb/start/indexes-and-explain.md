---
title: Indexes and performance
summary: Speed up queries with single, compound and text indexes, and read explain() to confirm an index is used.
takeaways:
- Without an index MongoDB scans every document (COLLSCAN)
- Compound indexes follow the order equality, sort, range
- explain('executionStats') shows if an index was used and how many documents were examined
---
## Why indexes

Without an index, a query reads **every document** in the collection (a *collection scan*). An index keeps the field sorted so MongoDB can jump to the answer. Only `_id` is indexed by default.

```javascript
db.students.createIndex({ email: 1 }, { unique: true })      // 1 = ascending
db.students.createIndex({ city: 1, marks: -1 })              // compound
db.articles.createIndex({ title: "text", body: "text" })     // text search
db.sessions.createIndex({ createdAt: 1 }, { expireAfterSeconds: 3600 })  // TTL: auto-delete
```

| Index | Use |
| --- | --- |
| Single field | filters and sorts on one field |
| **Compound** | filters on several fields together |
| **Unique** | no duplicates (an email) |
| **Text** | word search |
| **TTL** | automatically delete old documents (sessions, logs) |

## Check with explain

```javascript
db.students.find({ city: "Chennai" }).sort({ marks: -1 }).explain("executionStats")
```

Look at:

- **`winningPlan`**: `COLLSCAN` (no index) or `IXSCAN` (index used).
- **`totalDocsExamined`** compared with **`nReturned`**: ideally close. If it examines 1,000,000 to return 10, you need an index.

## Compound index order

For a query that filters on equality, then sorts, then uses a range, build the index in that order: **Equality, Sort, Range (the ESR rule)**. The index `{ city: 1, marks: -1 }` serves "city equals X, sorted by marks descending" very well.

## Cautions

- Every index uses memory and **slows writes**. Keep only those your queries use.
- Create indexes for the queries you actually run, found by looking at slow queries (the profiler or Atlas performance advisor).
- A query that uses fields in a different order or skips the leading field may not use the compound index.
