---
title: Lists, tuples, sets and dictionaries
summary: Questions on the built-in collections: copying, sorting, hashing and comprehensions.
kind: qa
takeaways:
- Lists and dicts are mutable; tuples are immutable
- Dict and set lookups are fast because they use hashing
- Know how to copy, deduplicate, reverse and sort
---
### Q [Easy] What is the difference between a list and a tuple?
A list is **mutable** and a tuple is **immutable**. Lists use `[]` and tuples use `()`. Tuples are slightly smaller and faster, and a tuple of immutable items can be used as a dictionary key.

### Q [Easy] What is the difference between a list and a set?
A list keeps order and allows duplicates. A set has no duplicates and no guaranteed order, and checking `x in my_set` is much faster than in a list.

### Q [Easy] How do you remove duplicates from a list?
`list(set(items))` works but loses the order. To keep the order:

```python
unique = list(dict.fromkeys(items))
```

### Q [Easy] How do you reverse a list or a string?
`items.reverse()` reverses a list in place. `items[::-1]` and `reversed(items)` give a reversed copy. For a string use `text[::-1]`.

### Q [Medium] How does a dictionary find a key so fast?
It stores keys in a **hash table**: the key's hash decides where the value sits, so a lookup takes about O(1) time on average.

### Q [Medium] Why can a list not be a dictionary key?
Keys must be **hashable**, which needs the hash to never change. A list is mutable, so it cannot be hashed. A tuple of numbers or strings can be.

### Q [Medium] What is the difference between a shallow copy and a deep copy?
A **shallow** copy (`copy.copy` or `list.copy()`) copies the outer container but shares the inner objects. A **deep** copy (`copy.deepcopy`) copies everything inside too.

```python
import copy
a = [[1, 2], [3]]
b = copy.copy(a)
b[0].append(99)
print(a)   # [[1, 2, 99], [3]]  the inner list is shared
```

### Q [Medium] What is the difference between `append` and `extend`?
`append(x)` adds `x` as **one item**. `extend(iterable)` adds **each element** of the iterable.

```python
a = [1]
a.append([2, 3])   # [1, [2, 3]]
b = [1]
b.extend([2, 3])   # [1, 2, 3]
```

### Q [Medium] What is a list comprehension and why use it?
A compact way to build a list from another: `[n * n for n in nums if n % 2 == 0]`. It is shorter and often faster than a loop with `append`.

### Q [Medium] How do you sort a list of dictionaries by a key?
Use `sorted` with a `key` function:

```python
users = [{"name": "A", "age": 30}, {"name": "B", "age": 25}]
by_age = sorted(users, key=lambda u: u["age"])
```

Add `reverse=True` for descending order.

:::practice leetcode
Many coding problems are about these collections. Practise in Coding Practice.
:::
