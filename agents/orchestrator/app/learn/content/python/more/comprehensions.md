---
title: Comprehensions and generators
summary: Build lists, dictionaries and sets in one readable line, and use generators to handle large data without filling memory.
takeaways:
- A comprehension is a short, readable way to build a collection from another
- Read it as: the result, then the loop, then the optional condition
- Generators produce one item at a time, which saves memory on big data
---
## Why comprehensions

Data work is full of "take a list, change or filter it, make a new list". A **list comprehension** does that in one line.

```python
marks = [92, 48, 85, 71, 64, 55]

squares = [m * m for m in range(1, 6)]
passed = [m for m in marks if m >= 60]
grades = ["Pass" if m >= 50 else "Fail" for m in marks]

print(squares)
print(passed)
print(grades)
```

```output
[1, 4, 9, 16, 25]
[92, 85, 71, 64]
['Pass', 'Fail', 'Pass', 'Pass', 'Pass', 'Pass']
```

**How to read it:** `[ result  for item in collection  if condition ]` means "give me `result` for every `item` in the collection, but only if the condition is true".

The same idea written as a normal loop, for comparison:

```python
passed = []
for m in marks:
    if m >= 60:
        passed.append(m)
print(passed)
```

```output
[92, 85, 71, 64]
```

Both give the same answer. The comprehension is shorter and says clearly what you want.

## Dictionary and set comprehensions

```python
names = ["asha", "ravi", "meena"]

lengths = {name: len(name) for name in names}                      # dictionary
initials = {name[0].upper() for name in names}                     # set (no duplicates)
by_name = {name.title(): mark for name, mark in zip(names, [92, 48, 85])}

print(lengths)
print(sorted(initials))
print(by_name)
```

```output
{'asha': 4, 'ravi': 4, 'meena': 5}
['A', 'M', 'R']
{'Asha': 92, 'Ravi': 48, 'Meena': 85}
```

## Two loops in one line

```python
pairs = [(a, b) for a in (1, 2, 3) for b in ("x", "y")]
print(pairs)

matrix = [[1, 2, 3], [4, 5, 6]]
flat = [value for row in matrix for value in row]
print(flat)
```

```output
[(1, 'x'), (1, 'y'), (2, 'x'), (2, 'y'), (3, 'x'), (3, 'y')]
[1, 2, 3, 4, 5, 6]
```

The loops read left to right, in the same order as nested `for` statements. More than two loops, or a long condition, is a sign to use a normal loop instead.

## Generators: one item at a time

A list comprehension builds the **whole list** in memory. A **generator expression** (round brackets) makes items **only when asked**:

```python
import sys

big_list = [n * n for n in range(1_000_000)]
big_generator = (n * n for n in range(1_000_000))

print("list uses more than 1 MB :", sys.getsizeof(big_list) > 1_000_000)
print("generator uses less than 1 KB:", sys.getsizeof(big_generator) < 1_000)
print("sum from the generator:", sum(big_generator))
```

```output
list uses more than 1 MB : True
generator uses less than 1 KB: True
sum from the generator: 333332833333500000
```

Both give the same total, but the generator never stores a million numbers. This matters when you read very large files or datasets.

## A generator function

```python
def read_in_batches(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]            # yield gives one batch, then pauses

for batch in read_in_batches(list(range(1, 8)), 3):
    print(batch)
```

```output
[1, 2, 3]
[4, 5, 6]
[7]
```

`yield` hands back one batch and waits. Machine learning code uses this idea to feed data to a model in batches.

## When not to use them

| Use a comprehension for | Use a normal loop for |
| --- | --- |
| simple filtering or transforming | several steps or side effects (printing, saving) |
| one clear idea per line | complicated conditions |
| building a new collection | code a beginner must debug |

:::tip
If you have to read a comprehension twice to understand it, split it into a loop. Clear code beats clever code.
:::
