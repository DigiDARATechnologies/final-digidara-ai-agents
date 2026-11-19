---
title: Reshaping and stacking
summary: Change an array's shape, flatten it, add axes, and join or split arrays.
takeaways:
- reshape changes the shape but not the data; -1 means work it out for me
- flatten and ravel make a 1D array; np.newaxis adds an axis
- concatenate, vstack and hstack join arrays
---
## reshape

The same 12 numbers can be arranged in different shapes, as long as the item count matches:

```python
import numpy as np

a = np.arange(12)
print(a.reshape(3, 4))
print(a.reshape(2, 6).shape)
print(a.reshape(4, -1).shape)       # -1: let NumPy work out the 3
```

```output
[[ 0  1  2  3]
 [ 4  5  6  7]
 [ 8  9 10 11]]
(2, 6)
(4, 3)
```

A shape that does not fit gives an error, because 12 items cannot fill a 5 by 3 grid.

## Turning a list into a column

Machine learning libraries often want features as a **column** of shape `(n, 1)`:

```python
hours = np.array([1, 2, 3, 4])
print(hours.shape)
print(hours.reshape(-1, 1).shape)
print(hours[:, np.newaxis].shape)
```

```output
(4,)
(4, 1)
(4, 1)
```

## Flattening

```python
grid = np.array([[1, 2, 3], [4, 5, 6]])
print(grid.flatten())               # a copy
print(grid.ravel())                 # a view when possible (faster)
```

```output
[1 2 3 4 5 6]
[1 2 3 4 5 6]
```

## Transpose

Swap the rows and columns:

```python
print(grid)
print(grid.T)
print(grid.T.shape)
```

```output
[[1 2 3]
 [4 5 6]]
[[1 4]
 [2 5]
 [3 6]]
(3, 2)
```

## Joining arrays

```python
a = np.array([[1, 2], [3, 4]])
b = np.array([[5, 6], [7, 8]])

print(np.vstack([a, b]))          # stack vertically (more rows)
print(np.hstack([a, b]))          # stack horizontally (more columns)
print(np.concatenate([a, b], axis=0).shape)
```

```output
[[1 2]
 [3 4]
 [5 6]
 [7 8]]
[[1 2 5 6]
 [3 4 7 8]]
(4, 2)
```

## Splitting

```python
data = np.arange(10)
first, second = np.split(data, 2)
print(first, second)
print(np.array_split(data, 3))
```

```output
[0 1 2 3 4] [5 6 7 8 9]
[array([0, 1, 2, 3]), array([4, 5, 6]), array([7, 8, 9])]
```

`split` needs equal parts; `array_split` allows uneven ones.

## Unique values and counting

```python
cities = np.array(["Chennai", "Salem", "Chennai", "Madurai", "Chennai"])
values, counts = np.unique(cities, return_counts=True)
print(values, counts)
```

```output
['Chennai' 'Madurai' 'Salem'] [3 1 1]
```

:::remember
When something goes wrong in a model, print `.shape`. A shape of `(100,)` and `(100, 1)` look alike but are different, and many functions only accept one of them.
:::
