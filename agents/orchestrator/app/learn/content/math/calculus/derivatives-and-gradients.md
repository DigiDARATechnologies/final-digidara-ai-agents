---
title: Derivatives and gradients
summary: Understand the derivative as a slope, the gradient as the direction of steepest climb, and why models need them to learn.
takeaways:
- The derivative is the slope of a function at a point
- The gradient collects the slopes for many inputs; it points uphill
- Training moves the weights opposite to the gradient to reduce the error
---
## The derivative is a slope

A **derivative** tells you how fast a function is changing at a point. For `f(x) = x²` the slope at `x = 3` is 6: if x grows by a tiny amount, f grows about 6 times as much.

You can check this numerically without any formulas by nudging x slightly:

```python
def f(x):
    return x ** 2

def slope(f, x, h=1e-6):
    return (f(x + h) - f(x - h)) / (2 * h)          # change in output / change in input

for x in (-2, 0, 3):
    print(f"slope of x^2 at x = {x:>2}: {slope(f, x):.3f}")
```

```output
slope of x^2 at x = -2: -4.000
slope of x^2 at x =  0: 0.000
slope of x^2 at x =  3: 6.000
```

The slope is negative on the left of zero (the curve goes down), zero at the bottom, and positive on the right. **A slope of zero marks a flat spot, a minimum or maximum.**

## A few rules (you will not need many)

| Function | Derivative |
| --- | --- |
| a constant, `5` | `0` |
| `x` | `1` |
| `x²` | `2x` |
| `xⁿ` | `n · xⁿ⁻¹` |
| `eˣ` | `eˣ` |
| `log x` | `1/x` |
| `c · f(x)` | `c · f′(x)` |
| `f(x) + g(x)` | `f′(x) + g′(x)` |

The **chain rule** handles a function inside a function: multiply the derivatives. It is the heart of backpropagation in neural networks.

```python
# chain rule: d/dx of (3x + 1)^2 = 2(3x + 1) * 3
x = 2
by_rule = 2 * (3 * x + 1) * 3
by_nudging = slope(lambda t: (3 * t + 1) ** 2, x)
print(by_rule, round(by_nudging, 3))
```

```output
42 42.0
```

## Why the slope matters for learning

A model has a **loss**: a number saying how wrong it is. Training wants the lowest loss. The slope of the loss tells us which way is downhill:

- slope positive: the loss rises as the weight rises, so **decrease** the weight,
- slope negative: **increase** the weight.

```python
def loss(w):
    return (w - 3) ** 2          # the best weight is 3

for w in (0, 3, 5):
    direction = "increase w" if slope(loss, w) < 0 else "decrease w" if slope(loss, w) > 0 else "stay"
    print(f"w = {w}: slope {slope(loss, w):>6.2f} -> {direction}")
```

```output
w = 0: slope  -6.00 -> increase w
w = 3: slope   0.00 -> stay
w = 5: slope   4.00 -> decrease w
```

## Partial derivatives and the gradient

When a function has several inputs, take the slope in **each direction separately** (a **partial derivative**). Collect them into a vector: the **gradient**.

For `f(x, y) = x² + 3y`, the partial slopes are `2x` and `3`, so the gradient at `(2, 5)` is `(4, 3)`.

```python
import numpy as np

def f2(p):
    x, y = p
    return x ** 2 + 3 * y

def gradient(f, p, h=1e-6):
    p = np.array(p, dtype=float)
    grad = np.zeros_like(p)
    for i in range(len(p)):
        step = np.zeros_like(p)
        step[i] = h
        grad[i] = (f(p + step) - f(p - step)) / (2 * h)
    return grad

print(np.round(gradient(f2, (2, 5)), 3))
```

```output
[4. 3.]
```

The gradient **points uphill** (the direction in which the function grows fastest). To reduce the loss, step the **opposite way**. A model with a million weights has a gradient with a million numbers, and libraries such as PyTorch compute it automatically.

:::remember
Slope tells you the direction. The gradient is the slope for many weights at once. Learning means repeatedly stepping against the gradient.
:::
