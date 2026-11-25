---
title: Lists and tuples
summary: Store many values in order; add, remove, slice, sort and loop.
takeaways:
- A list is ordered and changeable; a tuple is ordered and fixed
- Indexes start at 0, and negative indexes count from the end
- Common methods: append, remove, pop, sort
---
## Lists

A list holds several values in order:

```python
marks = [72, 85, 90]
print(marks[0])     # 72
print(marks[-1])    # 90
print(len(marks))   # 3
```

Lists are **mutable**: you can change them after creating them.

```python
marks.append(66)        # add at the end
marks.insert(0, 50)     # add at a position
marks.remove(85)        # remove the first 85
last = marks.pop()      # remove and return the last item
marks[0] = 55           # change an item
```

## Slicing and sorting

```python
nums = [5, 2, 9, 1]
print(nums[1:3])         # [2, 9]
print(sorted(nums))      # [1, 2, 5, 9]  (new list)
nums.sort()              # sorts nums itself
print(nums)              # [1, 2, 5, 9]
```

## Looping and checking

```python
for n in nums:
    print(n)

print(9 in nums)         # True
print(sum(nums), max(nums), min(nums))
```

## List comprehension

A short way to build a list from another:

```python
squares = [n * n for n in range(1, 6)]
print(squares)
```

```output
[1, 4, 9, 16, 25]
```

```python
evens = [n for n in range(10) if n % 2 == 0]
```

## Tuples

A tuple is like a list that cannot change:

```python
point = (3, 4)
x, y = point        # unpacking
```

Use tuples for values that belong together and should stay fixed, such as coordinates.

:::warning
Copying a list with `b = a` does not copy it. Both names point to the same list. Use `b = a.copy()` or `b = a[:]`.
:::

:::interview
**Interviewers often ask:** "List versus tuple?" Lists are mutable and tuples are immutable. Tuples can be dictionary keys; lists cannot.
:::
