---
title: Schema design: embed or reference?
summary: Decide how to model relationships in MongoDB, with the rules that keep documents fast and manageable.
takeaways:
- Embed data that is read together and belongs to one parent
- Reference data that is shared, large or growing without limit
- Design the schema around how the application reads the data
---
## Design from your queries

In SQL you normalise first and join later. In MongoDB you design the documents around **how the app reads data**. The main choice: **embed** or **reference**.

## Embed: put it inside

```javascript
{
  _id: 1,
  customer: "Asha",
  items: [
    { product: "Pen",  qty: 2, price: 10 },
    { product: "Book", qty: 1, price: 250 }
  ],
  total: 270
}
```

One read returns the whole order. Good when the data is **always read together**, is **owned** by the parent, and is **bounded** (an order has a few items).

## Reference: store the id

```javascript
// students
{ _id: 1, name: "Asha" }
// courses
{ _id: 10, title: "Python" }
// enrollments
{ studentId: 1, courseId: 10, joined: ISODate("2026-03-12") }
```

Good for **many-to-many** relationships, data used in many places, or lists that **grow without limit** (a user's thousands of log entries).

You combine them with `$lookup` (a join) in an aggregation, or with two queries.

## Decision table

| Question | Embed | Reference |
| --- | --- | --- |
| Always read together? | yes | no |
| Is it one-to-few? | yes | one-to-many large |
| Shared by many parents? | no | yes |
| Does the child change often on its own? | no | yes |
| Could it grow forever? | no | yes |

## Rules to remember

- A document has a **16 MB limit**, so never embed unbounded arrays.
- Embedding gives **fast reads** but repeats data; updating a repeated value means updating many documents.
- Copy a small amount of data on purpose when it speeds up reads (for example the course title in an enrollment), and accept the cost of keeping it in sync.
- Use **schema validation** to keep required fields and types consistent:

```javascript
db.createCollection("students", {
  validator: { $jsonSchema: {
    bsonType: "object",
    required: ["name", "marks"],
    properties: { marks: { bsonType: "int", minimum: 0, maximum: 100 } }
  } }
})
```

:::remember
"Data that is used together is stored together." Then reads need one trip to the database.
:::
