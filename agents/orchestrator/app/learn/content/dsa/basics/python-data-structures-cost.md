---
title: Python's built-in structures and their cost
summary: Know the speed of list, dict, set, deque and heap operations so you choose the right tool.
takeaways:
- list append is fast but insert at the front and `in` are slow
- dict and set lookups are O(1) on average
- collections.deque gives fast operations at both ends
---
## Why this matters

In an interview you rarely build structures from scratch. You pick the **right built-in** and know what its operations cost.

## The cheat sheet

| Structure | Operation | Cost |
| --- | --- | --- |
| **list** | `lst[i]`, `lst.append(x)`, `lst.pop()` | O(1) |
| | `lst.insert(0, x)`, `lst.pop(0)`, `x in lst`, `lst.remove(x)` | **O(n)** |
| | `sorted(lst)`, `lst.sort()` | O(n log n) |
| **dict** | get, set, delete, `key in d` | O(1) average |
| **set** | add, remove, `x in s` | O(1) average |
| **deque** | append / pop at either end | O(1) |
| **heapq** | push, pop smallest | O(log n) |
| **str** | `s + t` creates a new string | O(n) |

## The list trap

Removing from the **front** of a list shifts every other item. A `deque` does not.

```python
from collections import deque

q = deque([1, 2, 3])
q.append(4)           # add right
q.appendleft(0)       # add left
print(q)
print(q.popleft(), q.pop(), list(q))
```

```output
deque([0, 1, 2, 3, 4])
0 4 [1, 2, 3]
```

## Counting and grouping

```python
from collections import Counter, defaultdict

votes = ["a", "b", "a", "c", "a", "b"]
print(Counter(votes))
print(Counter(votes).most_common(1))

groups = defaultdict(list)
for word in ["tea", "eat", "ate", "tan", "nat"]:
    groups["".join(sorted(word))].append(word)
print(dict(groups))
```

```output
Counter({'a': 3, 'b': 2, 'c': 1})
[('a', 3)]
{'aet': ['tea', 'eat', 'ate'], 'ant': ['tan', 'nat']}
```

`Counter` counts, `defaultdict(list)` groups. Both are used in a huge number of interview problems.

## Sorting with a key

```python
students = [("Asha", 82), ("Ravi", 67), ("Meena", 91)]
print(sorted(students, key=lambda s: s[1], reverse=True))
```

```output
[('Meena', 91), ('Asha', 82), ('Ravi', 67)]
```

## String building

Joining strings with `+=` in a loop can be slow. Collect the pieces in a list and use `"".join(pieces)` once.

:::tip
Before writing a loop to check `x in some_list` repeatedly, turn the list into a **set** first. That one change often turns O(n squared) into O(n).
:::
