---
title: PyTorch tensors and autograd
summary: Meet PyTorch's tensor, the building block of every model, and its automatic differentiation engine that replaces hand-written backpropagation.
takeaways:
- A tensor is a NumPy-like array that can live on a GPU and track gradients
- Setting requires_grad=True makes PyTorch record operations so .backward() can compute gradients
- Wrap evaluation code in torch.no_grad() to save memory and speed
---
## Why PyTorch

Writing backpropagation by hand does not scale. **PyTorch** is the most popular deep learning library in research and increasingly in industry. It gives you:

- **tensors**: arrays that run on CPU or GPU,
- **autograd**: automatic gradients for any computation,
- **`torch.nn`**: ready-made layers, losses and optimisers.

```py
pip install torch
```

(Use the command from pytorch.org for your system if you want GPU support.)

## Tensors

A **tensor** is a multi-dimensional array, very much like a NumPy array.

```python
import numpy as np
import torch

a = torch.tensor([[1.0, 2.0, 3.0],
                  [4.0, 5.0, 6.0]])
print(a)
print("shape:", a.shape, "| dtype:", a.dtype, "| dimensions:", a.ndim)

print(torch.zeros(2, 3).shape, torch.ones(2).tolist(), torch.arange(5).tolist())
print(torch.linspace(0, 1, 5).tolist())
```

```output
tensor([[1., 2., 3.],
        [4., 5., 6.]])
shape: torch.Size([2, 3]) | dtype: torch.float32 | dimensions: 2
torch.Size([2, 3]) [1.0, 1.0] [0, 1, 2, 3, 4]
[0.0, 0.25, 0.5, 0.75, 1.0]
```

| Creation | Result |
| --- | --- |
| `torch.tensor(list)` | from data |
| `torch.zeros(2, 3)`, `torch.ones(...)` | filled with 0s or 1s |
| `torch.rand(2, 3)` | uniform random in [0, 1) |
| `torch.randn(2, 3)` | random from a standard normal distribution |
| `torch.arange(5)`, `torch.linspace(0, 1, 5)` | ranges |

## Operations and shapes

```python
a = torch.tensor([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
b = torch.tensor([10.0, 20.0, 30.0])

print((a + b).tolist())                 # broadcasting: b is added to every row
print((a * 2).tolist())
print((a @ a.T).tolist())               # matrix multiplication: (2,3) @ (3,2) -> (2,2)
print(a.sum().item(), a.mean().item(), a.max().item())
print(a.sum(dim=0).tolist(), a.sum(dim=1).tolist())      # per column, per row
print(a.reshape(3, 2).shape, a.view(-1).shape, a.T.shape)
print(a[0, 1].item(), a[:, 1].tolist(), a[a > 3].tolist())
```

```output
[[11.0, 22.0, 33.0], [14.0, 25.0, 36.0]]
[[2.0, 4.0, 6.0], [8.0, 10.0, 12.0]]
[[14.0, 32.0], [32.0, 77.0]]
21.0 3.5 6.0
[5.0, 7.0, 9.0] [6.0, 15.0]
torch.Size([3, 2]) torch.Size([6]) torch.Size([3, 2])
2.0 [2.0, 5.0] [4.0, 5.0, 6.0]
```

These behave just like NumPy: broadcasting, matrix multiplication with `@`, summing along a dimension (`dim`), reshaping, slicing and boolean masks.

## NumPy and PyTorch together

```python
array = np.array([1.0, 2.0, 3.0])
tensor = torch.from_numpy(array)          # shares memory with the array
back = tensor.numpy()

print(type(tensor).__name__, type(back).__name__)
print(torch.tensor([1, 2, 3]).dtype, torch.tensor([1.0, 2.0]).dtype, torch.tensor([1.0]).double().dtype)
```

```output
Tensor ndarray
torch.int64 torch.float32 torch.float64
```

Integers become `int64` and decimals become `float32` by default. Neural network weights are almost always `float32`. Mixing dtypes is a common cause of errors ("expected Float but found Double").

## Autograd: gradients for free

Mark a tensor with `requires_grad=True`, do any computation with it, call `.backward()`, and PyTorch fills `.grad` for you:

```python
x = torch.tensor(2.0, requires_grad=True)
y = x ** 2 + 3 * x          # y = x^2 + 3x, so dy/dx = 2x + 3

y.backward()
print("y =", y.item())
print("dy/dx at x = 2 is", x.grad.item())
```

```output
y = 10.0
dy/dx at x = 2 is 7.0
```

The slope at `x = 2` is `2 × 2 + 3 = 7`, and PyTorch got it with no formula from us. It works the same for a network with a billion operations: while computing the forward pass, PyTorch records a **computation graph**, then `.backward()` walks the graph in reverse, applying the chain rule.

## Gradients accumulate

```python
w = torch.tensor(1.0, requires_grad=True)

(3 * w).backward()
print("after first backward :", w.grad.item())
(3 * w).backward()
print("after second backward:", w.grad.item())    # added to the old value, not replaced!

w.grad.zero_()
print("after zero_()        :", w.grad.item())
```

```output
after first backward : 3.0
after second backward: 6.0
after zero_()        : 0.0
```

By design, `.backward()` **adds** to the existing gradients. In a training loop you must clear them each step (`optimizer.zero_grad()`), or gradients from previous batches pile up and the weights get wrong updates. This is one of the most common beginner bugs.

## Turning gradients off

When you only want predictions (testing, using a trained model), gradients are wasted work:

```python
w = torch.tensor(2.0, requires_grad=True)

with torch.no_grad():
    y = w * 10
print("requires_grad inside no_grad:", y.requires_grad)

z = (w * 10).detach()                 # cut a tensor out of the graph
print("detached tensor tracks grad :", z.requires_grad)
```

```output
requires_grad inside no_grad: False
detached tensor tracks grad : False
```

Use `torch.no_grad()` (or the slightly faster `torch.inference_mode()`) whenever you evaluate or predict. It saves memory and time.

## Devices: CPU and GPU

```python
device = "cuda" if torch.cuda.is_available() else "cpu"
print("training would run on:", device)

t = torch.ones(3).to(device)          # move a tensor; models move the same way: model.to(device)
print(t.device.type)
```

```output
training would run on: cpu
cpu
```

A GPU can be 10 to 100 times faster for large models. The rule: the model and all its input tensors must be on the **same device**, or you get an error. The small examples in this course run well on a CPU.

## Quick reference

| Task | Code |
| --- | --- |
| shape, dtype | `t.shape`, `t.dtype` |
| change shape | `t.reshape(...)`, `t.view(...)`, `t.unsqueeze(0)`, `t.squeeze()` |
| combine | `torch.cat([a, b])`, `torch.stack([a, b])` |
| gradients on | `torch.tensor(..., requires_grad=True)` |
| compute gradients | `loss.backward()` |
| clear gradients | `optimizer.zero_grad()` or `t.grad.zero_()` |
| no gradients | `with torch.no_grad():` |
| plain Python number | `t.item()` |
| to NumPy | `t.detach().cpu().numpy()` |

:::interview
**Interviewers often ask:** "What does `loss.backward()` do and why must we call `optimizer.zero_grad()`?" `backward()` computes the gradient of the loss with respect to every parameter that requires grad, by walking the recorded computation graph in reverse, and **adds** it into each parameter's `.grad`. Because gradients accumulate, you clear them before each new batch, otherwise old gradients contaminate the update.
:::
