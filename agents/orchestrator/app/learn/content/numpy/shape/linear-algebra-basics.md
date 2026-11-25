---
title: Linear algebra basics
summary: Dot products, matrix multiplication, transpose, inverse and solving equations: the maths behind machine learning.
takeaways:
- The dot product multiplies matching items and adds them up
- Use @ or np.dot for matrix multiplication; * is item by item
- np.linalg.solve finds the unknowns in a set of equations
---
## Why it matters

Machine learning is mostly linear algebra: a model multiplies your data by a table of numbers (the weights). NumPy has these tools built in.

## Dot product

```python
import numpy as np

prices = np.array([100, 250, 40])
quantities = np.array([2, 1, 5])
print(np.dot(prices, quantities))       # 100*2 + 250*1 + 40*5
```

```output
650
```

It multiplies matching items and adds them up: the total bill.

## Matrix multiplication

```python
A = np.array([[1, 2], [3, 4]])
B = np.array([[5, 6], [7, 8]])

print(A @ B)           # matrix product
print(A * B)           # item by item: a different thing!
```

```output
[[19 22]
 [43 50]]
[[ 5 12]
 [21 32]]
```

:::warning
`A * B` multiplies item by item. `A @ B` is the real matrix product. Mixing them up is one of the most common beginner mistakes.
:::

The matrix product needs the **inner sizes to match**: an `(m, n)` matrix times an `(n, k)` matrix gives an `(m, k)` matrix.

```python
X = np.ones((5, 3))
w = np.array([0.5, 1.0, 2.0])
print((X @ w).shape)
```

```output
(5,)
```

This is exactly how a linear model predicts: each row of `X` is one sample, `w` holds the weights, and `X @ w` gives all 5 predictions at once.

## Transpose, determinant and inverse

```python
A = np.array([[4.0, 2.0], [3.0, 1.0]])
print(A.T)
print(round(np.linalg.det(A), 2))
inverse = np.linalg.inv(A)
print(inverse.round(2))
print((A @ inverse).round(2))
```

```output
[[4. 3.]
 [2. 1.]]
-2.0
[[-0.5  1. ]
 [ 1.5 -2. ]]
[[1. 0.]
 [0. 1.]]
```

A matrix times its inverse gives the **identity matrix** (ones on the diagonal, zeros elsewhere).

## Solving equations

Finding the unknowns in a pair of equations is a classic linear algebra task. Here is one:

> 2x + y = 11
> x + 3y = 18

```python
coefficients = np.array([[2, 1],
                         [1, 3]])
constants = np.array([11, 18])
solution = np.linalg.solve(coefficients, constants)
print(solution)
print(coefficients @ solution)       # check: gives back 11 and 18
```

```output
[3. 5.]
[11. 18.]
```

So x = 3 and y = 5. Prefer `solve` to `inv(A) @ b`; it is faster and more accurate.

## Norms: the length of a vector

```python
v = np.array([3, 4])
print(np.linalg.norm(v))             # the length: sqrt(3^2 + 4^2)
```

```output
5.0
```

:::interview
**Interviewers often ask:** "What is the difference between `*` and `@` in NumPy?" `*` multiplies arrays item by item (with broadcasting). `@` performs matrix multiplication.
:::
