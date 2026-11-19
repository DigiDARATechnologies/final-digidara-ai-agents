---
title: Dictionaries and sets
summary: Look values up by key with dictionaries, and keep unique values with sets.
takeaways:
- A dictionary maps keys to values
- Use get() to avoid a KeyError
- A set keeps only unique items
---
## Dictionaries: look up by key

```python
student = {"name": "Asha", "age": 21, "city": "Chennai"}
print(student["name"])       # Asha
student["age"] = 22          # change
student["email"] = "a@x.com" # add
```

A key can be a string, number or tuple. Each key appears once.

## Safe reading

```python
print(student.get("phone"))            # None, no error
print(student.get("phone", "unknown")) # unknown
```

`student["phone"]` would raise a `KeyError`. `get()` returns a default instead.

## Looping

```python
for key in student:
    print(key, "=", student[key])

for key, value in student.items():
    print(key, value)
```

Useful methods: `keys()`, `values()`, `items()`, `pop(key)`, `del d[key]`.

## Counting with a dictionary

```python
text = "banana"
counts = {}
for ch in text:
    counts[ch] = counts.get(ch, 0) + 1
print(counts)
```

```output
{'b': 1, 'a': 3, 'n': 2}
```

## Sets: unique values

```python
tags = {"python", "sql", "python"}
print(tags)               # {'python', 'sql'}
tags.add("html")
print("sql" in tags)      # True
```

Sets ignore duplicates and are fast for "is this in there?" checks.

```python
a = {1, 2, 3}
b = {3, 4}
print(a | b)   # union {1, 2, 3, 4}
print(a & b)   # intersection {3}
print(a - b)   # difference {1, 2}
```

:::tip
To remove duplicates from a list, `list(set(items))` works, but the order is not kept.
:::

:::interview
**Interviewers often ask:** "How does a dictionary find a key so fast?" It uses a hash table: it hashes the key to jump straight to where the value is stored, so lookups are about O(1) on average.
:::
