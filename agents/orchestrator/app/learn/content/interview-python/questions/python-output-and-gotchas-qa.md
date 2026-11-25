---
title: Python output questions and gotchas
summary: Predict the output: mutable defaults, aliasing, closures, generators, copies and floating point.
kind: qa
takeaways:
- Read the code carefully and trace the state step by step
- Know the classic traps: mutable default arguments, aliasing and late binding
- Explain WHY, not just the output
---
Interviewers show small snippets and ask for the output. Try each before reading the answer.

### Q [Medium] What does this print? (mutable default argument)
```python
def add(x, items=[]):
    items.append(x)
    return items

print(add(1))
print(add(2))
```

```output
[1]
[1, 2]
```
The default list is created **once** when the function is defined and shared by all calls. Use `items=None` and create a new list inside the function.

### Q [Easy] What does this print? (aliasing)
```python
a = [1, 2]
b = a
b.append(3)
print(a, a is b)
c = a.copy()
c.append(4)
print(a, c)
```

```output
[1, 2, 3] True
[1, 2, 3] [1, 2, 3, 4]
```
`b = a` makes **another name for the same list**. `a.copy()` makes a new list.

### Q [Medium] What does this print? (late binding)
```python
funcs = [lambda: i for i in range(3)]
print([f() for f in funcs])

funcs = [lambda i=i: i for i in range(3)]
print([f() for f in funcs])
```

```output
[2, 2, 2]
[0, 1, 2]
```
The lambda looks up `i` **when it is called**, after the loop has ended (so i = 2). Binding `i=i` as a default captures the value at creation.

### Q [Medium] What does this print? (tuple with a list)
```python
t = (1, [2])
t[1].append(3)
print(t)
```

```output
(1, [2, 3])
```
The tuple is immutable, but the list **inside** is mutable, so it can change.

### Q [Medium] What does this print? (generators are used up)
```python
g = (x * x for x in range(3))
print(list(g))
print(list(g))
```

```output
[0, 1, 4]
[]
```
A generator can be consumed only **once**. The second `list(g)` is empty.

### Q [Medium] What does this print? (finally)
```python
def f():
    try:
        return "try"
    finally:
        print("cleanup")

print(f())
```

```output
cleanup
try
```
`finally` always runs, **before** the function actually returns.

### Q [Medium] What does this print? (shallow copy)
```python
import copy
a = [[1], [2]]
b = copy.copy(a)
b[0].append(9)
print(a)

c = copy.deepcopy(a)
c[0].append(7)
print(a, c)
```

```output
[[1, 9], [2]]
[[1, 9], [2]] [[1, 9, 7], [2]]
```
A shallow copy shares the inner lists, so changing `b[0]` changed `a`. The deep copy `c` is independent.

### Q [Easy] Why is `0.1 + 0.2 == 0.3` False?
```python
print(0.1 + 0.2 == 0.3)
print(round(0.1 + 0.2, 2) == 0.3)
import math
print(math.isclose(0.1 + 0.2, 0.3))
```

```output
False
True
True
```
Floats are stored in binary and cannot represent 0.1 exactly. Compare with `math.isclose` or use `decimal` for money.

### Q [Medium] What does this print? (slicing and indexing)
```python
nums = [10, 20, 30, 40, 50]
print(nums[1:4], nums[::-1][:2], nums[10:], nums[-2])
```

```output
[20, 30, 40] [50, 40] [] 40
```
Slices that go past the end do not raise errors, but an out-of-range **index** like `nums[10]` does.

### Q [Medium] What does this print? (dictionary behaviour)
```python
d = {"a": 1}
print(d.get("b"), d.get("b", 0), d.setdefault("c", 5), d)
```

```output
None 0 5 {'a': 1, 'c': 5}
```
`get` returns a default instead of raising `KeyError`; `setdefault` inserts the key if missing.

### Q [Hard] What does this print? (class variable vs instance variable)
```python
class Counter:
    count = 0
    def __init__(self):
        Counter.count += 1

a, b = Counter(), Counter()
print(Counter.count, a.count)
a.count = 10
print(Counter.count, a.count, b.count)
```

```output
2 2
2 10 2
```
`count` on the class is shared. Assigning `a.count = 10` creates a **new instance attribute** on `a` and hides the class one for `a` only.
