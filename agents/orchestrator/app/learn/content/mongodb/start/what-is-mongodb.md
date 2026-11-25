---
title: What is MongoDB?
summary: Meet MongoDB, a document database that stores flexible JSON-like records, and compare it with SQL tables.
takeaways:
- MongoDB stores documents (JSON-like) in collections instead of rows in tables
- Documents in one collection can have different fields, so the shape is flexible
- Choose it for flexible, nested data; choose SQL when relationships and strict rules matter most
---
## Documents instead of rows

A SQL database stores data in **tables** with fixed columns. **MongoDB** stores **documents**: JSON-like records that can hold nested data and lists.

```javascript
{
  _id: ObjectId("65f1a2b3c4d5e6f708192a3b"),
  name: "Asha",
  marks: 82,
  skills: ["python", "sql"],
  address: { city: "Chennai", pin: "600001" }
}
```

| SQL | MongoDB |
| --- | --- |
| database | database |
| table | **collection** |
| row | **document** |
| column | **field** |
| join | embedding, `$lookup` |
| primary key | `_id` (added automatically) |

A **collection** does not force every document to have the same fields, which makes it easy to change your data as the app grows. (You can still add validation rules later.)

## When to use it

| Good fit | Poor fit |
| --- | --- |
| content, catalogues, profiles with varying fields | many-to-many data with lots of joins |
| nested data that is read together (an order with its items) | strict banking-style rules across many records |
| fast-changing structure, quick prototypes | complex reporting with heavy joins |

Neither is "better". Many systems use both.

## Start using it

Use **MongoDB Atlas** (free cloud cluster) or install it locally, then open **mongosh**, the shell:

```javascript
use college                      // switch to (or create) a database
db.students.insertOne({ name: "Asha", marks: 82 })
db.students.find()
```

```output
[ { _id: ObjectId('65f1...'), name: 'Asha', marks: 82 } ]
```

A database and collection are created the first time you save data into them.

:::note
MongoDB shell and drivers use JavaScript-style syntax. If you know JSON, you already know the data format.
:::
