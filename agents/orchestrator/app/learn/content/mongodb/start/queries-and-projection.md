---
title: Queries, operators and projection
summary: Filter with comparison and logical operators, search arrays and nested fields, then sort, limit and choose fields.
takeaways:
- Comparison operators: $gt, $gte, $lt, $lte, $in, $ne
- Use dot notation for nested fields and $or / $and for logic
- Projection picks the fields to return; sort, skip and limit shape the result
---
## Sample data

```javascript
db.students.insertMany([
  { name: "Asha",  marks: 82, city: "Chennai", skills: ["python", "sql"] },
  { name: "Ravi",  marks: 67, city: "Madurai", skills: ["java"] },
  { name: "Meena", marks: 91, city: "Chennai", skills: ["python", "ml", "sql"] }
])
```

## Comparison operators

```javascript
db.students.find({ marks: { $gte: 70 } })              // 70 or more
db.students.find({ city: { $in: ["Chennai", "Madurai"] } })
db.students.find({ marks: { $gt: 60, $lt: 90 } })      // between 60 and 90
```

## Logical operators

```javascript
db.students.find({ $or: [ { city: "Madurai" }, { marks: { $gt: 90 } } ] })
db.students.find({ city: "Chennai", marks: { $gt: 85 } })   // AND is the default
```

## Arrays and nested fields

```javascript
db.students.find({ skills: "python" })                     // array contains python
db.students.find({ skills: { $all: ["python", "sql"] } })  // contains both
db.students.find({ "address.city": "Chennai" })            // dot notation for nested
db.students.find({ skills: { $size: 3 } })
```

## Projection: choose the fields

```javascript
db.students.find({ city: "Chennai" }, { name: 1, marks: 1, _id: 0 })
```

```output
[ { name: 'Asha', marks: 82 }, { name: 'Meena', marks: 91 } ]
```

`1` includes a field, `0` excludes it. Returning fewer fields saves bandwidth.

## Sort, skip, limit

```javascript
db.students.find().sort({ marks: -1 }).limit(2)     // top 2 by marks (-1 is descending)
db.students.find().sort({ name: 1 }).skip(10).limit(10)   // page 2
```

## Text matching

```javascript
db.students.find({ name: { $regex: "^a", $options: "i" } })   // starts with a, any case
```

Regular expressions that do not start with `^` cannot use an index well, so use them carefully on large data.
