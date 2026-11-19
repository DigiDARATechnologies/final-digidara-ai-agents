---
title: Creating arrays
summary: Make arrays from lists, ranges, zeros, ones and evenly spaced numbers, and read their shape and type.
takeaways:
- np.array converts a list; zeros, ones, arange and linspace build arrays directly
- shape, ndim, size and dtype describe an array
- Every item in an array has the same dtype
---
## From a list

```python
import numpy as np

a = np.array([1, 2, 3, 4])                     # one dimension
b = np.array([[1, 2, 3], [4, 5, 6]])           # two dimensions: 2 rows, 3 columns
print(a)
print(b)
```

```output
[1 2 3 4]
[[1 2 3]
 [4 5 6]]
```

## Describing an array

```python
print("shape:", b.shape)       # (rows, columns)
print("ndim :", b.ndim)        # number of dimensions
print("size :", b.size)        # total number of items
print("dtype:", b.dtype)       # the type of each item
```

```output
shape: (2, 3)
ndim : 2
size : 6
dtype: int32
```

## Building arrays directly

```python
print(np.zeros(4))
print(np.ones((2, 3)))
print(np.full((2, 2), 7))
print(np.eye(3))                 # identity matrix
```

```output
[0. 0. 0. 0.]
[[1. 1. 1.]
 [1. 1. 1.]]
[[7 7]
 [7 7]]
[[1. 0. 0.]
 [0. 1. 0.]
 [0. 0. 1.]]
```

## Ranges and evenly spaced numbers

```python
print(np.arange(0, 10, 2))       # start, stop (not included), step
print(np.linspace(0, 1, 5))      # 5 numbers from 0 to 1, both included
```

```output
[0 2 4 6 8]
[0.   0.25 0.5  0.75 1.  ]
```

| Function | Use it when |
| --- | --- |
| `np.arange(start, stop, step)` | you know the **step** |
| `np.linspace(start, stop, count)` | you know **how many** points you want |

:::warning
`arange` with decimal steps can surprise you: tiny rounding errors can make the last item appear or disappear unexpectedly. Prefer `linspace` when the steps are decimals.
:::

## Data types

All items in an array share one type:

```python
ints = np.array([1, 2, 3])
floats = np.array([1, 2, 3.5])          # one decimal makes every item a float
text = np.array(["a", "bb"])
print(ints.dtype, floats.dtype, text.dtype)
print(ints.astype(float))
```

```output
int32 float64 <U2
[1. 2. 3.]
```

You can choose a smaller type to save memory, for example `np.array([1, 2, 3], dtype=np.int8)`.

## Copying arrays

```python
x = np.array([1, 2, 3])
y = x                   # not a copy: two names for the same array
z = x.copy()            # a real, separate copy
x[0] = 99
print(y, z)
```

```output
[99  2  3] [1 2 3]
```

:::remember
`y = x` does not copy the data. Use `.copy()` when you want an independent array.
:::
