---
title: Transactions, replication and sharding
summary: Understand how MongoDB stays available and scales: replica sets, sharding, write concern and multi-document transactions.
takeaways:
- A replica set keeps copies of the data so the database survives a server failure
- Sharding splits a large collection across servers to scale
- Single-document operations are atomic; use transactions only when several documents must change together
---
## Atomicity in MongoDB

A write to **one document** is always atomic, even when it changes nested fields and arrays. This is another reason to embed data that changes together.

When several documents must change together (transfer money between two accounts), use a **multi-document transaction**:

```javascript
const session = db.getMongo().startSession();
session.startTransaction();
try {
  const accounts = session.getDatabase("bank").accounts;
  accounts.updateOne({ owner: "Asha" }, { $inc: { balance: -500 } });
  accounts.updateOne({ owner: "Ravi" }, { $inc: { balance: 500 } });
  session.commitTransaction();
} catch (e) {
  session.abortTransaction();
}
```

Transactions need a replica set. They cost performance, so a good schema that avoids them is better.

## Replica sets: availability

A **replica set** is a group of servers holding the same data:

- one **primary** receives all writes
- **secondaries** copy the data
- if the primary fails, the others **elect a new primary** automatically (usually within seconds)

Applications can read from secondaries to spread load, but those reads may be slightly **behind**.

## Write concern and read concern

| Setting | Meaning |
| --- | --- |
| `w: 1` | acknowledged by the primary only (fast) |
| `w: "majority"` | acknowledged by most servers (safe, survives failover) |
| read concern `majority` | read only data that is safely committed |

Use `w: "majority"` for data you cannot lose.

## Sharding: scaling out

When one server cannot hold or serve all the data, **sharding** splits a collection across several servers (shards) using a **shard key**.

- A good shard key spreads data and queries **evenly** and appears in most queries.
- A bad key (such as a timestamp that only grows) sends all new writes to one shard.
- The shard key is hard to change later, so choose carefully.

```text
app -> mongos (router) -> shard 1 | shard 2 | shard 3
```

## Summary

| Need | Feature |
| --- | --- |
| survive a server failure | replica set |
| more data or traffic than one server | sharding |
| change several documents together | transaction |
| never lose acknowledged data | write concern majority |

:::note
Most student projects only need a free Atlas cluster, which is already a replica set. Sharding matters at very large scale.
:::
