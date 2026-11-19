---
title: Indexing and slicing
summary: Pick items, rows, columns and blocks from arrays, and know when a slice is a view of the same data.
takeaways:
- Indexes start at 0 and negative indexes count from the end
- In 2D use array[row, column]
- A slice is a view: changing it changes the original
---
## One dimension

It works like a Python list:

```python
import numpy as np

a = np.array([10, 20, 30, 40, 50, 60])
print(a[0], a[-1])
print(a[1:4])         # items 1, 2, 3
print(a[::2])         # every second item
print(a[::-1])        # reversed
```

```output
10 60
[20 30 40]
[10 30 50]
[60 50 40 30 20 10]
```

## Two dimensions

Use `array[row, column]`:

```python
grid = np.array([
    [1, 2, 3, 4],
    [5, 6, 7, 8],
    [9, 10, 11, 12],
])
print(grid[1, 2])         # row 1, column 2
print(grid[0])            # the whole first row
print(grid[:, 1])         # every row, column 1
print(grid[1:, 2:])       # rows from 1, columns from 2
```

```output
7
[1 2 3 4]
[ 2  6 10]
[[ 7  8]
 [11 12]]
```

The colon `:` means "all". So `grid[:, 1]` reads "all rows, column 1".

## Picking with a list of positions

```python
print(a[[0, 2, 5]])
print(grid[[0, 2], 1])
```

```output
[10 30 60]
[ 2 10]
```

## Slices are views

A slice shares memory with the original array. Changing the slice changes the original:

```python
original = np.array([1, 2, 3, 4, 5])
part = original[1:4]
part[0] = 99
print(original)
```

```output
[ 1 99  3  4  5]
```

If you want an independent piece, copy it:

```python
safe = original[1:4].copy()
safe[0] = -1
print(original)
```

```output
[ 1 99  3  4  5]
```

:::warning
This surprises people coming from lists, where a slice is always a new list. With NumPy, use `.copy()` when you plan to change a slice and keep the original safe.
:::

## Changing values

```python
grid = np.arange(1, 13).reshape(3, 4)
grid[0, 0] = 100
grid[:, -1] = 0           # set the last column to 0
print(grid)
```

```output
[[100   2   3   0]
 [  5   6   7   0]
 [  9  10  11   0]]
```

| You want | Write |
| --- | --- |
| one item | `a[i, j]` |
| a row | `a[i]` or `a[i, :]` |
| a column | `a[:, j]` |
| a block | `a[r1:r2, c1:c2]` |
| the last item | `a[-1]` |
