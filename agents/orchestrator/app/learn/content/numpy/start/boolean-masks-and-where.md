---
title: Boolean masks and where
summary: Select and change values by condition, count matches, and choose between two values with np.where.
takeaways:
- A comparison gives an array of True and False; use it to pick items
- Combine conditions with & and |, each in brackets
- np.where(condition, a, b) picks a or b for every item
---
## Select by condition

A comparison checks every item and returns True or False:

```python
import numpy as np

marks = np.array([92, 78, 85, 66, 88, 71])
mask = marks >= 80
print(mask)
print(marks[mask])          # only the True items
```

```output
[ True False  True False  True False]
[92 85 88]
```

You will use this constantly. In one line you filter a whole array.

## Combining conditions

Use `&` for and, `|` for or, `~` for not. **Every condition needs its own brackets.**

```python
print(marks[(marks >= 70) & (marks < 90)])
print(marks[(marks < 70) | (marks > 90)])
print(marks[~(marks >= 80)])
```

```output
[78 85 88 71]
[92 66]
[78 66 71]
```

:::warning
Do not use the words `and` or `or` between arrays. Python cannot decide whether a whole array is true and raises a `ValueError`. Use `&` and `|` with brackets.
:::

## Counting what matches

`True` counts as 1, so you can sum a mask:

```python
print((marks >= 80).sum())         # how many
print((marks >= 80).mean())        # what share
print(np.any(marks > 90), np.all(marks > 60))
```

```output
3
0.5
True True
```

## Changing values by condition

```python
curved = marks.copy()
curved[curved < 70] = 70           # lift everyone below 70 up to 70
print(curved)
```

```output
[92 78 85 70 88 71]
```

## np.where: choose between two values

`np.where(condition, if_true, if_false)` works on every item:

```python
result = np.where(marks >= 75, "Pass", "Fail")
print(result)
print(np.where(marks >= 80, marks, 0))
```

```output
['Pass' 'Pass' 'Pass' 'Fail' 'Pass' 'Fail']
[92  0 85  0 88  0]
```

With only a condition, it gives the **positions** where it is true:

```python
print(np.where(marks >= 80))
print(marks.argmax(), marks.argmin())
```

```output
(array([0, 2, 4], dtype=int64),)
0 3
```

`argmax` and `argmin` give the position of the largest and smallest values.

:::tip
Whenever you catch yourself writing a loop with an `if` inside to build a new list, try `np.where` or a mask instead. It is shorter and far faster.
:::
