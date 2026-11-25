---
title: Updating arrays and nested data
summary: Add, remove and change items inside arrays and nested objects with $push, $pull, $addToSet and the positional operator.
takeaways:
- $push adds to an array, $addToSet adds only if missing, $pull removes
- The positional operator $ updates the matched array element
- You can update nested fields with dot notation
---
## Add and remove array items

```javascript
db.students.updateOne({ name: "Ravi" }, { $push: { skills: "sql" } })
db.students.updateOne({ name: "Ravi" }, { $addToSet: { skills: "sql" } })   // no duplicate
db.students.updateOne({ name: "Ravi" }, { $pull: { skills: "java" } })      // remove
db.students.updateOne({ name: "Ravi" }, { $pop: { skills: 1 } })            // remove last
```

| Operator | Effect |
| --- | --- |
| `$push` | append (duplicates allowed) |
| `$addToSet` | append only if not already there |
| `$pull` | remove all matching items |
| `$pop` | remove the first (`-1`) or last (`1`) item |

## Arrays of objects

```javascript
{ name: "Asha", subjects: [ { name: "maths", marks: 80 }, { name: "physics", marks: 70 } ] }
```

Find students with a subject scored above 75 using `$elemMatch`, which tests **one element** against **all** conditions:

```javascript
db.students.find({ subjects: { $elemMatch: { name: "maths", marks: { $gt: 75 } } } })
```

Update the matched element with the **positional operator** `$`:

```javascript
db.students.updateOne(
  { name: "Asha", "subjects.name": "physics" },
  { $set: { "subjects.$.marks": 78 } }
)
```

## Nested fields

```javascript
db.students.updateOne({ name: "Asha" }, { $set: { "address.city": "Salem" } })
```

Dot notation changes just that field and leaves the rest of the nested object alone.

:::tip
Without `$elemMatch`, two conditions on an array can be satisfied by **different** elements, which is rarely what you want.
:::
