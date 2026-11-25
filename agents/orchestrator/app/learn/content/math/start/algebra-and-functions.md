---
title: Algebra and functions
summary: Revise the algebra a machine learning model is built from: variables, equations, functions, straight lines, exponents and logarithms.
takeaways:
- A function turns an input into an output, and a model is a function with learnable numbers inside
- A straight line y = m x + c is the simplest model; m is the slope and c the intercept
- Exponents and logarithms appear everywhere in ML (sigmoid, loss functions, learning curves)
---
## Why this matters

You do not need to become a mathematician. You need to read a formula without fear. Almost every ML idea is one of these:

| Idea | Math behind it |
| --- | --- |
| a model | a **function** with numbers to learn |
| learning | finding the best numbers (**calculus**) |
| data | **vectors and matrices** (linear algebra) |
| uncertainty | **probability and statistics** |

## Variables and equations

A variable is a name for a number that can change. An **equation** says two things are equal. To solve it, do the same thing to both sides.

```python
# solve 3x + 5 = 20
x = (20 - 5) / 3
print("x =", x)
print("check:", 3 * x + 5)
```

```output
x = 5.0
check: 20.0
```

## Functions

A **function** takes an input and gives one output: `f(x) = 2x + 1`.

```python
def f(x):
    return 2 * x + 1

for x in (0, 1, 2, 3):
    print(f"f({x}) = {f(x)}")
```

```output
f(0) = 1
f(1) = 3
f(2) = 5
f(3) = 7
```

A machine learning model is exactly this, with a lot more inputs and with the numbers (2 and 1 here) **learned from data**.

## The straight line

`y = m x + c`

| Part | Meaning | Example |
| --- | --- | --- |
| `m` (slope) | how much `y` changes when `x` goes up by 1 | m = 8: each extra study hour adds 8 marks |
| `c` (intercept) | the value of `y` when `x` is 0 | c = 20: the score with no study |

```python
import numpy as np

hours = np.array([1, 2, 3, 4, 5])
m, c = 8, 30                                  # a simple model: marks = 8 * hours + 30
predicted = m * hours + c
print(predicted)
```

```output
[38 46 54 62 70]
```

Linear regression is just the search for the best `m` and `c`. With many inputs the line becomes `y = m1·x1 + m2·x2 + ... + c`.

## Exponents and roots

| Idea | Meaning | Example |
| --- | --- | --- |
| `x^2` | x times x | 4^2 = 16 |
| `x^0.5` or `√x` | the square root | √16 = 4 |
| `x^-1` | one divided by x | 4^-1 = 0.25 |
| `e^x` | growth by the special number e (about 2.718) | used in the sigmoid |

## Logarithms

A **logarithm** answers: "what power gives this number?" `log10(1000) = 3` because 10^3 = 1000. Logs turn multiplication into addition and squash huge ranges.

```python
import math

print(math.log10(1000), math.log2(8), round(math.log(math.e), 1))
print("log turns products into sums:", round(math.log(6), 4), "=", round(math.log(2) + math.log(3), 4))
print("income of 25,000 and 900,000 in log10:", round(math.log10(25000), 2), "and", round(math.log10(900000), 2))
```

```output
3.0 3.0 1.0
log turns products into sums: 1.7918 = 1.7918
income of 25,000 and 900,000 in log10: 4.4 and 5.95
```

You met logs in feature engineering (taming big numbers) and in the cross-entropy loss of deep learning.

## The sigmoid: a function you will meet again

The sigmoid squeezes any number into the range 0 to 1, so it can be read as a probability:

```python
def sigmoid(z):
    return 1 / (1 + math.exp(-z))

for z in (-4, -1, 0, 1, 4):
    print(f"sigmoid({z:>2}) = {sigmoid(z):.3f}")
```

```output
sigmoid(-4) = 0.018
sigmoid(-1) = 0.269
sigmoid( 0) = 0.500
sigmoid( 1) = 0.731
sigmoid( 4) = 0.982
```

Large negative inputs give nearly 0, zero gives exactly 0.5, and large positive inputs give nearly 1. Logistic regression and neural networks use it.

:::remember
You only need three things from algebra: a function maps inputs to outputs, a line is `m x + c`, and exponents and logs are tools that reshape numbers.
:::
