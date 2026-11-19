---
title: Array maths and broadcasting
summary: Calculate on whole arrays, use maths functions, and let NumPy stretch smaller arrays to fit with broadcasting.
takeaways:
- Operators work item by item on arrays of the same shape
- Broadcasting stretches a smaller array so the shapes fit
- Arrays follow the same rules whether they have 1 or many dimensions
---
## Item by item

```python
import numpy as np

a = np.array([1, 2, 3])
b = np.array([10, 20, 30])
print(a + b)
print(a * b)         # item by item, not a matrix product
print(b / a)
print(a ** 2)
```

```output
[11 22 33]
[10 40 90]
[10. 10. 10.]
[1 4 9]
```

## Maths functions

```python
x = np.array([1, 4, 9, 16])
print(np.sqrt(x))
print(np.exp([0, 1, 2]).round(3))
print(np.log([1, np.e, 10]).round(3))
print(np.round([2.567, 3.141], 1), np.floor(2.7), np.ceil(2.1))
```

```output
[1. 2. 3. 4.]
[1.    2.718 7.389]
[0.    1.    2.303]
[2.6 3.1] 2.0 3.0
```

## Broadcasting: arrays of different shapes

What happens when the shapes differ? NumPy **stretches** the smaller array to match when the shapes are compatible.

A number is stretched across the whole array:

```python
prices = np.array([100, 250, 400])
print(prices * 1.18)        # add 18% tax to every price
```

```output
[118. 295. 472.]
```

A row can be stretched down a table:

```python
table = np.array([[1, 2, 3],
                  [4, 5, 6],
                  [7, 8, 9]])
row = np.array([10, 20, 30])
print(table + row)
```

```output
[[11 22 33]
 [14 25 36]
 [17 28 39]]
```

A column stretches across it:

```python
column = np.array([[100], [200], [300]])
print(table + column)
```

```output
[[101 102 103]
 [204 205 206]
 [307 308 309]]
```

:::formula
**Broadcasting rule.** Compare the shapes from the **right**. Two sizes are compatible if they are **equal** or one of them is **1**. A size of 1 is stretched to match the other.
:::

| Shapes | Result | Why |
| --- | --- | --- |
| (3, 3) and (3,) | (3, 3) | the row of 3 is stretched down |
| (3, 3) and (3, 1) | (3, 3) | the column is stretched across |
| (3, 3) and (4,) | error | 3 and 4 are neither equal nor 1 |

```python
try:
    table + np.array([1, 2, 3, 4])
except ValueError as error:
    print("ValueError:", error)
```

```output
ValueError: operands could not be broadcast together with shapes (3,3) (4,)
```

## A practical use: normalising columns

Scale each column of a table so it has an average of 0:

```python
data = np.array([[10.0, 200.0], [20.0, 400.0], [30.0, 600.0]])
centred = data - data.mean(axis=0)      # subtract each column's mean
print(centred)
```

```output
[[ -10. -200.]
 [   0.    0.]
 [  10.  200.]]
```

:::remember
When you get "operands could not be broadcast together", print the `.shape` of both arrays. The mismatch is almost always visible straight away.
:::
