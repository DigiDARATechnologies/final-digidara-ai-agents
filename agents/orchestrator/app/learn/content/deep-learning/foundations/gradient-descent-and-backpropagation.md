---
title: Gradient descent and backpropagation
summary: Understand how a network learns: follow the slope downhill with gradient descent, and compute every weight's gradient with the chain rule, checked against PyTorch.
takeaways:
- The gradient says how the loss changes if you nudge a weight; step the opposite way to reduce the loss
- The learning rate sets the size of each step: too small is slow, too large overshoots
- Backpropagation is the chain rule applied layer by layer, from the loss back to every weight
---
## Walking downhill in fog

Imagine standing on a hilly field in thick fog, trying to reach the lowest point. You cannot see far, but you can feel the **slope** under your feet. So you take a step **downhill**, feel the slope again, and repeat. That is **gradient descent**. The height of the ground is the **loss**, and your position is the **weights**. The slope is the **gradient**.

## Gradient descent on one weight

Take a loss `L(w) = (w − 3)²`. Its lowest point is at `w = 3`. The slope is `2 (w − 3)`. Step against the slope:

```python
w = 0.0
learning_rate = 0.1

for step in range(1, 11):
    gradient = 2 * (w - 3)                  # the slope at the current position
    w = w - learning_rate * gradient        # step downhill
    print(f"step {step:>2}: w = {w:.4f}   loss = {(w - 3) ** 2:.4f}")
```

```output
step  1: w = 0.6000   loss = 5.7600
step  2: w = 1.0800   loss = 3.6864
step  3: w = 1.4640   loss = 2.3593
step  4: w = 1.7712   loss = 1.5099
step  5: w = 2.0170   loss = 0.9664
step  6: w = 2.2136   loss = 0.6185
step  7: w = 2.3709   loss = 0.3958
step  8: w = 2.4967   loss = 0.2533
step  9: w = 2.5973   loss = 0.1621
step 10: w = 2.6779   loss = 0.1038
```

`w` moves towards 3, in big steps at first (where the slope is steep) and smaller ones as the ground flattens out. The update rule is always: **new weight = old weight − learning rate × gradient**.

## The learning rate

| Learning rate | What happens |
| --- | --- |
| too small | steady, but painfully slow |
| just right | smooth and quick |
| too large | overshoots the bottom, bounces around, or **diverges** (the loss explodes) |

```python
def run(learning_rate, steps=8):
    w = 0.0
    for _ in range(steps):
        w = w - learning_rate * 2 * (w - 3)
    return w

for lr in (0.01, 0.1, 0.9, 1.1):
    print(f"learning rate {lr:>4}: after 8 steps w = {run(lr):.3f}   (target 3)")
```

```output
learning rate 0.01: after 8 steps w = 0.448   (target 3)
learning rate  0.1: after 8 steps w = 2.497   (target 3)
learning rate  0.9: after 8 steps w = 2.497   (target 3)
learning rate  1.1: after 8 steps w = -9.899   (target 3)
```

With 0.01 the weight has barely moved (0.45 after 8 steps). With 0.1 it creeps in towards 3 from one side. With 0.9 each step **overshoots** to the other side of 3 and back, so after an even number of steps it happens to land at the same 2.497, but the path is a zigzag, not a smooth walk. With 1.1 every step overshoots **more** than the last, so `w` flies away from 3 (to about −9.9). The learning rate is the most important setting in all of deep learning.

## Many weights, one gradient each

A real network has millions of weights. Each one gets its **own** gradient: the slope of the loss in that weight's direction. Together they form the gradient vector. Every weight is updated with the same rule at the same time.

## Backpropagation: how the gradients are found

A network is a chain of simple steps: weights, then sums, then activations, then loss. To find how the loss depends on an early weight, we use the **chain rule** of calculus: multiply the slopes of each step along the chain, working **backwards** from the loss.

A tiny network by hand: one input `x = 2`, one hidden neuron with ReLU, one output, target `y = 10`.

```python
x, y = 2.0, 10.0
w1, w2 = 1.5, 0.5

# forward pass
z = w1 * x                       # 3.0
h = max(0.0, z)                  # ReLU: 3.0
y_hat = w2 * h                   # 1.5
loss = (y_hat - y) ** 2          # 72.25

# backward pass: the chain rule, one step at a time, from the loss back to each weight
d_yhat = 2 * (y_hat - y)         # how the loss changes with the prediction
d_w2 = d_yhat * h                # y_hat = w2 * h, so d y_hat / d w2 = h
d_h = d_yhat * w2                # d y_hat / d h = w2
d_z = d_h * (1.0 if z > 0 else 0.0)   # the ReLU passes the gradient only where it was active
d_w1 = d_z * x                   # z = w1 * x, so d z / d w1 = x

print("loss          :", loss)
print("gradient of w2:", d_w2)
print("gradient of w1:", d_w1)
```

```output
loss          : 72.25
gradient of w2: -51.0
gradient of w1: -17.0
```

Both gradients are negative, meaning "increasing these weights will lower the loss", which is right: the prediction (1.5) is far below the target (10), so the weights should grow.

## Checking against PyTorch's automatic version

Doing this by hand for a network with millions of weights is impossible, so libraries do it automatically (**autograd**). Let us confirm our hand calculation matches:

```python
import torch

w1_t = torch.tensor(1.5, requires_grad=True)
w2_t = torch.tensor(0.5, requires_grad=True)
x_t, y_t = torch.tensor(2.0), torch.tensor(10.0)

loss_t = (w2_t * torch.relu(w1_t * x_t) - y_t) ** 2
loss_t.backward()                                  # backpropagation, done for us

print("PyTorch gradient of w2:", w2_t.grad.item())
print("PyTorch gradient of w1:", w1_t.grad.item())
print("matches our hand calculation:", w2_t.grad.item() == d_w2 and w1_t.grad.item() == d_w1)
```

```output
PyTorch gradient of w2: -51.0
PyTorch gradient of w1: -17.0
matches our hand calculation: True
```

They match exactly. **Backpropagation is nothing magical**: it is the chain rule, applied efficiently, caching the intermediate values from the forward pass.

## One full update

```python
learning_rate = 0.01
w1_new = w1 - learning_rate * d_w1
w2_new = w2 - learning_rate * d_w2

new_loss = (w2_new * max(0.0, w1_new * x) - y) ** 2
print("loss before:", loss)
print("loss after one step:", round(new_loss, 3))
```

```output
loss before: 72.25
loss after one step: 43.912
```

The loss dropped from 72.25 to a smaller value after a single update. Repeating **forward pass, loss, backward pass, update** is training.

## Stochastic and mini-batch gradient descent

Computing the gradient over the **whole** dataset for every step is slow. In practice:

| Method | Gradient computed from | Notes |
| --- | --- | --- |
| **Batch** gradient descent | all examples | exact but slow, memory heavy |
| **Stochastic** (SGD) | one example | fast but very noisy |
| **Mini-batch** | a small batch (32, 64, 256...) | the standard: a good balance of speed and stability |

One pass through the whole dataset is an **epoch**. Training for 20 epochs on 1,000 examples with a batch size of 100 means 10 updates per epoch, 200 in all.

:::remember
The training loop, in four lines of thought: **predict, measure the error, work out each weight's blame (backpropagation), nudge each weight (gradient descent).** Everything else in deep learning is a refinement of these four.
:::

:::interview
**Interviewers often ask:** "Explain backpropagation." After a forward pass computes the loss, backpropagation applies the chain rule from the output back to the input, multiplying local derivatives layer by layer, to get the gradient of the loss with respect to every weight in one backward sweep. Gradient descent then updates each weight against its gradient.
:::
