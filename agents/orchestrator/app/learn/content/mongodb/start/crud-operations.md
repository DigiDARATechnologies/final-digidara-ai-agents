---
title: CRUD: create, read, update, delete
summary: Insert, find, update and delete documents with the core MongoDB commands.
takeaways:
- insertOne and insertMany create documents
- find with a filter reads; updateOne with $set changes fields
- deleteOne and deleteMany remove documents; always pass a filter
---
## Create

```javascript
db.students.insertOne({ name: "Asha", marks: 82, city: "Chennai" })

db.students.insertMany([
  { name: "Ravi",  marks: 67, city: "Madurai" },
  { name: "Meena", marks: 91, city: "Chennai" }
])
```

Each document gets a unique `_id` automatically.

## Read

```javascript
db.students.find()                          // all documents
db.students.find({ city: "Chennai" })       // filter
db.students.findOne({ name: "Ravi" })       // first match
db.students.countDocuments({ marks: { $gte: 75 } })
```

```output
[
  { _id: ObjectId('...'), name: 'Asha',  marks: 82, city: 'Chennai' },
  { _id: ObjectId('...'), name: 'Meena', marks: 91, city: 'Chennai' }
]
```

The first argument is the **filter** (like `WHERE`).

## Update

Use an **update operator** such as `$set`. Without one you would replace the whole document.

```javascript
db.students.updateOne({ name: "Ravi" }, { $set: { marks: 72 } })
db.students.updateMany({ city: "Chennai" }, { $inc: { marks: 2 } })    // add 2 to marks
db.students.updateOne({ name: "Kavi" }, { $set: { marks: 60 } }, { upsert: true }) // insert if missing
```

| Operator | Meaning |
| --- | --- |
| `$set` | set or add a field |
| `$unset` | remove a field |
| `$inc` | add to a number |
| `$rename` | rename a field |

## Delete

```javascript
db.students.deleteOne({ name: "Ravi" })
db.students.deleteMany({ marks: { $lt: 35 } })
```

:::warning
`deleteMany({})` with an empty filter deletes **every** document. Check a filter with `find` first.
:::
