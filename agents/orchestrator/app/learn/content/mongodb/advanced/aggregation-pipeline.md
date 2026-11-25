---
title: The aggregation pipeline
summary: Transform and summarise data in stages with $match, $group, $sort, $project and $lookup.
takeaways:
- An aggregation is a pipeline: each stage transforms the documents and passes them on
- $match early, $group to summarise, $sort and $project to shape the output
- $lookup joins another collection
---
## The idea

`find` returns documents. **Aggregation** lets you filter, group, calculate and reshape them in **stages**, like an assembly line. Each stage's output is the next stage's input.

Sample `orders`: `{ customer, city, amount, status }`.

```javascript
db.orders.aggregate([
  { $match: { status: "paid" } },                       // 1. keep paid orders
  { $group: {                                           // 2. group by city
      _id: "$city",
      orders: { $sum: 1 },
      revenue: { $sum: "$amount" },
      average: { $avg: "$amount" }
  } },
  { $sort: { revenue: -1 } },                           // 3. biggest first
  { $limit: 3 }                                         // 4. top 3
])
```

```output
[ { _id: 'Chennai', orders: 12, revenue: 48200, average: 4016.67 },
  { _id: 'Madurai', orders: 7,  revenue: 21000, average: 3000 },
  { _id: 'Salem',   orders: 4,  revenue: 9800,  average: 2450 } ]
```

(Numbers shown are example output.)

## Common stages

| Stage | Like in SQL | Purpose |
| --- | --- | --- |
| `$match` | WHERE | filter documents |
| `$group` | GROUP BY | group and calculate |
| `$sort` | ORDER BY | order |
| `$limit` / `$skip` | LIMIT / OFFSET | paging |
| `$project` | SELECT | choose or compute fields |
| `$lookup` | JOIN | bring in another collection |
| `$unwind` | | turn an array into one document per item |
| `$addFields` | | add calculated fields |

## $lookup: a join

```javascript
db.orders.aggregate([
  { $lookup: { from: "customers", localField: "customerId", foreignField: "_id", as: "customer" } },
  { $unwind: "$customer" },
  { $project: { amount: 1, "customer.name": 1 } }
])
```

## $unwind: count by array item

```javascript
db.students.aggregate([
  { $unwind: "$skills" },
  { $group: { _id: "$skills", students: { $sum: 1 } } },
  { $sort: { students: -1 } }
])
```

This answers "which skill is most common?".

## Performance tips

- Put **`$match` and `$limit` as early as possible** so later stages handle fewer documents. An early `$match` can use an index.
- Avoid unnecessary `$lookup` on huge collections; sometimes embedding is better.

:::interview What is the aggregation pipeline?
A sequence of stages ($match, $group, $sort, $project, $lookup and more) where each stage transforms the documents and passes the result to the next. It is MongoDB's way to do grouping, calculation and joins.
:::
