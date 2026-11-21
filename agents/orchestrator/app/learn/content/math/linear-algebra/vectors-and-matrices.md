---
title: Vectors and matrices
summary: See how data becomes vectors and matrices, and learn dot products and matrix multiplication, the calculation behind every model.
takeaways:
- A vector is a list of numbers; a matrix is a table of numbers
- The dot product multiplies matching numbers and adds them up: it is how a model combines features
- Matrix multiplication does many dot products at once, which is why ML is fast
---
## Data as numbers in a grid

One student described by three numbers (study hours, attendance, previous score) is a **vector**. A whole class is a **matrix**: one row per student, one column per feature.

```python
import numpy as np

student = np.array([4.5, 92, 78])             # a vector with 3 features
class_data = np.array([[4.5, 92, 78],
                       [1.0, 55, 40],
                       [3.0, 75, 60]])         # a matrix: 3 students x 3 features

print("vector shape:", student.shape)
print("matrix shape:", class_data.shape)
```

```output
vector shape: (3,)
matrix shape: (3, 3)
```

Shape `(3, 3)` means 3 rows and 3 columns. Reading shapes is the most useful linear algebra skill.

## Vector operations

```python
a = np.array([1, 2, 3])
b = np.array([4, 5, 6])

print("add      :", a + b)
print("multiply by 2:", a * 2)
print("length   :", round(float(np.linalg.norm(a)), 3))
```

```output
add      : [5 7 9]
multiply by 2: [2 4 6]
length   : 3.742
```

## The dot product

Multiply matching numbers and add: `1×4 + 2×5 + 3×6 = 32`.

```python
print(np.dot(a, b))
print(1 * 4 + 2 * 5 + 3 * 6)
```

```output
32
32
```

**This is what a model does.** To predict a student's score, multiply each feature by a **weight** (how important it is) and add them up:

```python
weights = np.array([6.0, 0.3, 0.4])           # how much each feature matters
bias = 10
score = np.dot(student, weights) + bias
print("predicted score:", round(float(score), 1))
```

```output
predicted score: 95.8
```

The dot product also measures similarity: two vectors pointing the same way give a large dot product (used in search and in attention).

## Matrix multiplication

Multiply a matrix by a vector, and you get one dot product per row, which means the predictions for **every student at once**:

```python
predictions = class_data @ weights + bias
print(np.round(predictions, 1))
```

```output
[95.8 48.5 74.5]
```

The `@` operator is matrix multiplication. A neural network layer is exactly `inputs @ weights + bias`.

## The shape rule

For `A @ B` to work, the **inner sizes must match**, and the result has the **outer sizes**:

| A | B | Result |
| --- | --- | --- |
| (3, 3) | (3,) | (3,) |
| (5, 4) | (4, 2) | (5, 2) |
| (2, 3) | (2, 3) | **error** (3 does not match 2) |

```python
A = np.ones((5, 4))
B = np.ones((4, 2))
print((A @ B).shape)

try:
    np.ones((2, 3)) @ np.ones((2, 3))
except ValueError:
    print("error: the inner sizes 3 and 2 do not match")
```

```output
(5, 2)
error: the inner sizes 3 and 2 do not match
```

## Other terms you will hear

| Term | Meaning |
| --- | --- |
| **transpose** (`A.T`) | swap rows and columns |
| **identity matrix** | ones on the diagonal; multiplying by it changes nothing |
| **inverse** | the matrix that undoes another; used to solve equations |
| **eigenvalues and eigenvectors** | the main directions of a matrix; the idea behind PCA |

```python
M = np.array([[1, 2], [3, 4]])
print(M.T)
print(M @ np.eye(2))
```

```output
[[1 3]
 [2 4]]
[[1. 2.]
 [3. 4.]]
```

:::remember
Features form a vector, a dataset forms a matrix, and prediction is a matrix multiplication with the weights. If the shapes line up, the model can run.
:::
