---
title: Gradient descent in action
summary: Watch gradient descent find the best line for some data, see what the learning rate does, and check the answer against the exact solution.
takeaways:
- Gradient descent repeats: compute the gradient, step against it, and check the loss
- The learning rate sets the step size: too small is slow, too large overshoots
- The result matches the exact least-squares answer, which proves the method works
---
## The idea

Imagine standing on a hill in fog and wanting to reach the bottom. You feel the slope under your feet and step downhill, again and again. That is **gradient descent**.

`new weight = old weight − learning rate × gradient`

## Fit a line to data

We have study hours and marks, and want the best `marks = m × hours + c`.

```python
import numpy as np

hours = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
marks = np.array([38.0, 46.0, 57.0, 63.0, 74.0, 83.0])

m, c = 0.0, 0.0                    # start with a bad guess
learning_rate = 0.05

print("step    m      c      loss")
for step in range(0, 3001):
    prediction = m * hours + c
    error = prediction - marks
    loss = np.mean(error ** 2)                   # mean squared error
    if step in (0, 1, 10, 100, 1000, 3000):
        print(f"{step:>5}  {m:>5.2f}  {c:>5.2f}  {loss:>8.2f}")
    grad_m = 2 * np.mean(error * hours)          # slope of the loss with respect to m
    grad_c = 2 * np.mean(error)                  # slope of the loss with respect to c
    m -= learning_rate * grad_m
    c -= learning_rate * grad_c
```

```output
step    m      c      loss
    0   0.00   0.00   3857.17
    1  23.68   6.02   1455.81
   10  13.81   7.69     85.50
  100   9.93  24.67      3.96
 1000   9.00  28.67      0.89
 3000   9.00  28.67      0.89
```

The loss starts large and falls with every step, quickly at first and then slowly as the slope flattens near the bottom. The weights keep settling long after the loss looks small, so real training runs many steps.

## Check against the exact answer

For a straight line there is an exact solution (least squares). Gradient descent should land on it:

```python
exact_m, exact_c = np.polyfit(hours, marks, 1)
print("gradient descent:", round(m, 2), round(c, 2))
print("exact solution  :", round(exact_m, 2), round(exact_c, 2))
```

```output
gradient descent: 9.0 28.67
exact solution  : 9.0 28.67
```

The two answers agree. For complicated models there is no exact formula, so gradient descent is the only practical method.

## The learning rate

```python
def train(learning_rate, steps=60):
    m, c = 0.0, 0.0
    for _ in range(steps):
        error = m * hours + c - marks
        m -= learning_rate * 2 * np.mean(error * hours)
        c -= learning_rate * 2 * np.mean(error)
    return np.mean((m * hours + c - marks) ** 2)

for lr in (0.001, 0.02, 0.06, 0.09):
    result = train(lr)
    print(f"learning rate {lr:<6}: loss after 60 steps = " + (f"{result:.1f}" if result < 1e6 else "exploded (the steps overshoot more each time)"))
```

```output
learning rate 0.001 : loss after 60 steps = 193.4
learning rate 0.02  : loss after 60 steps = 51.6
learning rate 0.06  : loss after 60 steps = 9.6
learning rate 0.09  : loss after 60 steps = exploded (the steps overshoot more each time)
```

| Learning rate | What happens |
| --- | --- |
| too small | very slow progress (the loss barely falls) |
| just right | smooth, fast progress |
| too large | steps overshoot the bottom, and the loss grows instead of shrinking |

## Variants you will hear about

| Name | Idea |
| --- | --- |
| **Batch** gradient descent | uses all the data for each step (what we did) |
| **Stochastic (SGD)** | uses one example per step: noisy but fast |
| **Mini-batch** | uses a small batch: the usual choice |
| **Momentum, Adam** | add memory so steps are smoother and faster (the deep learning course) |

:::interview
**Interviewers often ask:** "What is gradient descent and what does the learning rate do?" An algorithm that repeatedly moves the model's weights a small step against the gradient of the loss to reduce it. The learning rate is the step size: too small is slow, too large can overshoot or diverge.
:::
