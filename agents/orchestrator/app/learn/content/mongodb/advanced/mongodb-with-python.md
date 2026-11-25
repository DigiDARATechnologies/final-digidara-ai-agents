---
title: MongoDB with Python
summary: Connect to MongoDB from Python with PyMongo, run CRUD and aggregation, and keep credentials safe.
takeaways:
- PyMongo is the official Python driver
- Collections work like in the shell, with dictionaries instead of JSON
- Keep the connection string in an environment variable, never in code
---
## Install and connect

```bash
pip install pymongo
```

```python
import os
from pymongo import MongoClient

client = MongoClient(os.environ["MONGODB_URI"])   # the connection string from Atlas
db = client["college"]
students = db["students"]
```

Never put the connection string (it contains a password) in your code or in Git. Store it in an environment variable or a `.env` file that is git-ignored.

## CRUD in Python

```python
students.insert_one({"name": "Asha", "marks": 82, "skills": ["python", "sql"]})
students.insert_many([{"name": "Ravi", "marks": 67}, {"name": "Meena", "marks": 91}])

for doc in students.find({"marks": {"$gte": 70}}, {"_id": 0}).sort("marks", -1):
    print(doc)

students.update_one({"name": "Ravi"}, {"$set": {"marks": 72}})
students.delete_one({"name": "Ravi"})
```

Filters and operators are the same as in the shell, written as Python dictionaries.

## Aggregation

```python
pipeline = [
    {"$match": {"marks": {"$gte": 60}}},
    {"$group": {"_id": None, "average": {"$avg": "$marks"}, "count": {"$sum": 1}}},
]
print(list(students.aggregate(pipeline)))
```

## Indexes

```python
students.create_index("email", unique=True)
```

## ObjectId

The `_id` is an `ObjectId`, not a string. To look a document up by an id from a URL, convert it:

```python
from bson import ObjectId
students.find_one({"_id": ObjectId(id_from_url)})
```

## Safe input

MongoDB can suffer **NoSQL injection** if you pass user-supplied JSON straight into a filter (a user sends `{"$ne": null}` as a password). Always take plain values, check their types, and build the filter yourself:

```python
password = str(request_data["password"])      # force a string, not a dictionary
students.find_one({"email": email, "password_hash": hash_of(password)})
```

## ODMs

For larger apps, libraries such as **Motor** (async) or **Beanie / MongoEngine** give you models and validation. PyMongo is enough to learn and for small projects.

:::tip
Mini project: a notes or expense tracker API with Flask and PyMongo. It combines Flask, JSON and MongoDB, and looks good on a portfolio.
:::
