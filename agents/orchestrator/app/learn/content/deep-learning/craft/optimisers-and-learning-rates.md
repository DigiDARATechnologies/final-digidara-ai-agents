---
title: Optimisers and learning rates
summary: Go beyond plain gradient descent with momentum and Adam, learn how to choose a learning rate, and use schedules to train better.
takeaways:
- The optimiser decides how gradients become weight updates; Adam is a strong default
- The learning rate is the most important hyperparameter: try values on a log scale
- Learning rate schedules (decay, warm-up) usually improve the final result
---
## What an optimiser does

Backpropagation gives each weight a gradient. The **optimiser** turns that into an actual change to the weight. Plain gradient descent just does `weight -= learning_rate × gradient`. Smarter optimisers keep a little memory to move faster and more smoothly.

| Optimiser | Idea | When to use |
| --- | --- | --- |
| **SGD** | the plain rule above | simple; with momentum it is still the best for many vision models |
| **SGD + momentum** | keeps a running "velocity" so it rolls through flat spots and smooths noisy gradients | image models, with careful learning rate tuning |
| **RMSprop** | scales each step by the recent size of that weight's gradients | recurrent networks, older code |
| **Adam** | momentum **and** a per-weight step size | **the default choice**: works well with little tuning |
| **AdamW** | Adam with weight decay done correctly | **the standard for transformers** and most modern models |

## A fair race

We train the same small network from the same starting weights with three optimisers, and compare the training loss:

```python
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

data = load_breast_cancer()
X_train, X_test, y_train, y_test = train_test_split(data.data, data.target, test_size=0.25, random_state=0, stratify=data.target)
scaler = StandardScaler().fit(X_train)
X_train, X_test = scaler.transform(X_train), scaler.transform(X_test)
Xt, yt = torch.tensor(X_train, dtype=torch.float32), torch.tensor(y_train, dtype=torch.float32)
Xv, yv = torch.tensor(X_test, dtype=torch.float32), torch.tensor(y_test, dtype=torch.float32)

def train(make_optimizer, epochs=10, seed=0):
    torch.manual_seed(seed)
    model = nn.Sequential(nn.Linear(30, 16), nn.ReLU(), nn.Linear(16, 1))
    optimizer = make_optimizer(model.parameters())
    loss_fn = nn.BCEWithLogitsLoss()
    loader = DataLoader(TensorDataset(Xt, yt), batch_size=32, shuffle=True, generator=torch.Generator().manual_seed(seed))
    history = []
    for epoch in range(epochs):
        for xb, yb in loader:
            loss = loss_fn(model(xb).squeeze(1), yb)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        with torch.no_grad():
            history.append(loss_fn(model(Xt).squeeze(1), yt).item())
    return history

runs = {
    "SGD, lr 0.01": lambda p: torch.optim.SGD(p, lr=0.01),
    "SGD + momentum 0.9": lambda p: torch.optim.SGD(p, lr=0.01, momentum=0.9),
    "Adam, lr 0.01": lambda p: torch.optim.Adam(p, lr=0.01),
}
print("training loss after epoch:      1      3     10")
for name, make in runs.items():
    h = train(make)
    print(f"{name:<22}  {h[0]:.3f}  {h[2]:.3f}  {h[9]:.3f}")
```

```output
training loss after epoch:      1      3     10
SGD, lr 0.01            0.698  0.621  0.423
SGD + momentum 0.9      0.551  0.227  0.075
Adam, lr 0.01           0.174  0.059  0.030
```

Same network, same data, same starting point: only the optimiser differs. Plain SGD with this small learning rate is the slowest. Momentum helps a lot, and Adam gets lowest quickest. Adam's per-weight step sizes mean it needs less tuning, which is why it is the default.

## The learning rate matters most

```python
print("Adam, loss after 10 epochs for different learning rates")
for lr in (1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1.0):
    h = train(lambda p: torch.optim.Adam(p, lr=lr))
    print(f"  lr {lr:>7}: {h[-1]:.3f}")
```

```output
Adam, loss after 10 epochs for different learning rates
  lr   1e-05: 0.733
  lr  0.0001: 0.634
  lr   0.001: 0.176
  lr    0.01: 0.030
  lr     0.1: 0.004
  lr     1.0: 1.376
```

Very small rates (0.00001, 0.0001) barely learn in 10 epochs. Rates from 0.001 to 0.1 all work, with the lowest *training* loss here at 0.1. And at 1.0 training breaks down (the loss is far worse than where it started). Two lessons: the usable range spans **orders of magnitude**, so search on a **log scale** (0.0001, 0.001, 0.01...), not in even steps; and the rate with the lowest training loss is not automatically the best one, because very large rates are often unstable on bigger problems and you should judge on **validation** data. `0.001` is a safe default for Adam.

| Rule of thumb | Starting value |
| --- | --- |
| Adam / AdamW | `1e-3`, or `3e-4` (try `1e-4` for fine-tuning big pretrained models) |
| SGD with momentum | `0.1` to `0.01` |
| big transformer training | `1e-4` to `5e-4`, with warm-up and decay |
| fine-tuning a pretrained model | `1e-5` to `5e-5` |

## Learning rate schedules

A rate that is good at the start is often too large near the end, when the weights need fine adjustment. A **schedule** changes the rate during training:

```python
model = nn.Linear(2, 1)
optimizer = torch.optim.SGD(model.parameters(), lr=0.1)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=10)

rates = []
for epoch in range(10):
    rates.append(optimizer.param_groups[0]["lr"])
    optimizer.step()
    scheduler.step()
print([round(r, 4) for r in rates])
```

```output
[0.1, 0.0976, 0.0905, 0.0794, 0.0655, 0.05, 0.0345, 0.0206, 0.0095, 0.0024]
```

The cosine schedule starts at 0.1 and glides smoothly towards 0. It is widely used.

| Schedule | Idea |
| --- | --- |
| **step decay** (`StepLR`) | cut the rate by a factor every few epochs |
| **cosine annealing** | smooth decay following a cosine curve |
| **warm-up** | start tiny and **increase** for the first steps; protects big models early on |
| **reduce on plateau** (`ReduceLROnPlateau`) | cut the rate when the validation loss stops improving |
| **one cycle** | rise then fall; often trains fast |

## Other useful tools

| Tool | Purpose |
| --- | --- |
| **weight decay** (`weight_decay=0.01` in `AdamW`) | a small penalty on large weights (regularisation) |
| **gradient clipping** (`torch.nn.utils.clip_grad_norm_(params, 1.0)`) | caps the gradient size to prevent explosions, vital for RNNs and transformers |
| **batch size** | larger batches give smoother gradients and faster epochs on a GPU, small batches add noise that can help generalisation |
| **mixed precision** (`torch.autocast`) | uses 16-bit numbers on a GPU for speed and memory savings |

:::tip
When a model will not train, **change one thing at a time**, starting with the learning rate. Try 10 times smaller and 10 times larger and compare the loss curves. This single experiment solves a surprising share of training problems.
:::

:::interview
**Interviewers often ask:** "What does Adam do differently from SGD?" Adam keeps running averages of each weight's gradient (momentum) and of its squared gradient (scale), giving each weight an adaptive step size, so it converges quickly with little tuning. "How do you pick a learning rate?" Try values on a log scale, watch the loss curves, and add a schedule (warm-up then decay) for large models.
:::
