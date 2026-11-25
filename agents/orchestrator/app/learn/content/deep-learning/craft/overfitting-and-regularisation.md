---
title: Overfitting and regularisation in neural networks
summary: Watch a large network memorise noise, then tame it with dropout, weight decay, early stopping and data augmentation.
takeaways:
- Overfitting shows up as training loss falling while validation loss rises
- Dropout, weight decay, early stopping and more data all reduce it
- Always keep a validation set and watch its curve during training
---
## The problem

A neural network with many parameters can **memorise** the training data, noise and all, instead of learning the real pattern. It then does very well on data it has seen and poorly on new data. This is **overfitting**, and large networks are especially prone to it.

Let us provoke it: a big network, with only 60 noisy training points.

```python
import numpy as np
import torch
from torch import nn
from sklearn.datasets import make_moons

X_all, y_all = make_moons(n_samples=1060, noise=0.35, random_state=0)
Xt, yt = torch.tensor(X_all[:60], dtype=torch.float32), torch.tensor(y_all[:60], dtype=torch.float32)
Xv, yv = torch.tensor(X_all[60:], dtype=torch.float32), torch.tensor(y_all[60:], dtype=torch.float32)
print("training points:", len(Xt), " validation points:", len(Xv))

def make_model(dropout=0.0):
    torch.manual_seed(0)
    return nn.Sequential(nn.Linear(2, 256), nn.ReLU(), nn.Dropout(dropout),
                         nn.Linear(256, 256), nn.ReLU(), nn.Dropout(dropout),
                         nn.Linear(256, 1))

loss_fn = nn.BCEWithLogitsLoss()

def scores(model, X, y):
    model.eval()
    with torch.no_grad():
        logits = model(X).squeeze(1)
        return loss_fn(logits, y).item(), ((logits > 0).float() == y).float().mean().item()
```

```output
training points: 60  validation points: 1000
```

## Watch the curves diverge

```python
model = make_model()
optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

print("epoch | train loss  train acc | val loss  val acc")
history = []
for epoch in range(1, 401):
    model.train()
    loss = loss_fn(model(Xt).squeeze(1), yt)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    train_loss, train_acc = scores(model, Xt, yt)
    val_loss, val_acc = scores(model, Xv, yv)
    history.append((epoch, val_loss))
    if epoch in (10, 30, 100, 400):
        print(f"{epoch:>5} | {train_loss:>10.3f}  {train_acc:>9.2f} | {val_loss:>8.3f}  {val_acc:>7.2f}")

best_epoch, best_loss = min(history, key=lambda h: h[1])
print(f"validation loss was lowest at epoch {best_epoch} ({best_loss:.3f}), then got worse")
```

```output
epoch | train loss  train acc | val loss  val acc
   10 |      0.225       0.88 |    0.304     0.88
   30 |      0.113       0.93 |    0.435     0.88
  100 |      0.011       1.00 |    1.785     0.87
  400 |      0.000       1.00 |    3.234     0.86
validation loss was lowest at epoch 14 (0.267), then got worse
```

This is the signature of overfitting:

- The **training** loss keeps falling towards zero and training accuracy reaches 100%: the network has memorised the 60 points.
- The **validation** loss reached its lowest point early, then **rose**, and the validation accuracy stopped improving.

The network learned the pattern first, then started memorising noise. The gap between the two curves is the overfitting.

## The cures

| Method | How it helps |
| --- | --- |
| **More data** | the surest cure: harder to memorise |
| **Early stopping** | stop at the epoch where validation loss is lowest |
| **Dropout** | randomly switch off neurons during training so none can be relied upon alone |
| **Weight decay (L2)** | penalise large weights, which favours smoother functions |
| **Smaller model** | fewer parameters, less capacity to memorise |
| **Data augmentation** | create more varied training examples (flip, crop, add noise) |
| **Batch normalisation** | adds slight noise, a mild regulariser |
| **Ensembles** | average several models |

## Dropout, weight decay and early stopping together

**Dropout** randomly zeroes a fraction of the neurons on every training step (and does nothing when evaluating). **Early stopping** keeps the weights from the best validation epoch.

```python
import copy

model = make_model(dropout=0.3)
optimizer = torch.optim.AdamW(model.parameters(), lr=0.01, weight_decay=0.05)

best_val, best_state, wait, patience = float("inf"), None, 0, 40
for epoch in range(1, 401):
    model.train()
    loss = loss_fn(model(Xt).squeeze(1), yt)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    val_loss, val_acc = scores(model, Xv, yv)
    if val_loss < best_val:
        best_val, best_state, wait, best_epoch = val_loss, copy.deepcopy(model.state_dict()), 0, epoch
    else:
        wait += 1
        if wait >= patience:                       # no improvement for 40 epochs: stop
            break

model.load_state_dict(best_state)                  # go back to the best weights
val_loss, val_acc = scores(model, Xv, yv)
print(f"stopped at epoch {epoch}; best epoch was {best_epoch}")
print(f"validation loss {val_loss:.3f}   validation accuracy {val_acc:.2f}")
```

```output
stopped at epoch 58; best epoch was 18
validation loss 0.267   validation accuracy 0.90
```

Compare with the unregularised network at the end of its training (validation loss 3.234, accuracy 0.86): the regularised, early-stopped model ends with a validation loss of 0.267 and accuracy 0.90. To be fair, the unregularised model also touched 0.267 at epoch 14, so **early stopping alone captures most of the gain here**. Dropout and weight decay make the damage from over-training smaller and the curve flatter, which matters more on larger, noisier problems. In practice you combine them and always keep the best-validation weights.

## How dropout works, in numbers

```python
torch.manual_seed(0)
layer = nn.Dropout(p=0.5)
x = torch.ones(10)

layer.train()
print("training:", layer(x).tolist())
layer.eval()
print("eval    :", layer(x).tolist())
```

```output
training: [0.0, 0.0, 2.0, 0.0, 0.0, 0.0, 2.0, 2.0, 0.0, 2.0]
eval    : [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
```

In training mode about half the values are zeroed, and the survivors are **doubled** (scaled by 1/(1−p)) so the total signal stays the same on average. In evaluation mode nothing is changed.

## Data augmentation

For images, simple random changes create "new" examples for free:

```py
from torchvision import transforms

train_transform = transforms.Compose([
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(10),
    transforms.RandomResizedCrop(224, scale=(0.8, 1.0)),
    transforms.ColorJitter(brightness=0.2, contrast=0.2),
    transforms.ToTensor(),
])
```

The network sees a slightly different version of each picture every epoch, so it cannot memorise exact pixels. Apply augmentation to the **training** data only, never to validation or test data. For text and audio there are equivalents (word swaps, back-translation, noise, time stretching).

## A practical routine

1. Always hold out a **validation set** and plot training and validation loss every epoch.
2. If both are high: the model is too small or training is too short (underfitting).
3. If training is low and validation high: overfitting. Add data, augmentation, dropout, weight decay; reduce size; use early stopping.
4. Keep a final **test set** untouched until the very end.

:::warning
Do not use the **test** set for early stopping or choosing hyperparameters. That quietly tunes your model to the test data and makes your final score too optimistic. Use the validation set for decisions and the test set once.
:::

:::interview
**Interviewers often ask:** "How do you detect and fix overfitting in a neural network?" Detect it when training loss keeps decreasing while validation loss rises. Fix it with more data and augmentation, dropout, weight decay, a smaller model, batch normalisation and early stopping, always judging on a held-out validation set.
:::
