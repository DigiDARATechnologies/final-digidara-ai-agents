---
title: The training loop and data loading
summary: Write the standard PyTorch training loop end to end: datasets, DataLoader, loss, optimiser, evaluation, on a real dataset.
takeaways:
- Every PyTorch training loop is the same: forward, loss, zero_grad, backward, step
- Dataset and DataLoader handle batching and shuffling
- Evaluate on held-out data with model.eval() and no_grad, and keep track of metrics per epoch
---
## The recipe

Every PyTorch training loop has the same five steps inside two loops (epochs, then batches):

```py
for epoch in range(n_epochs):
    for inputs, targets in train_loader:
        predictions = model(inputs)             # 1. forward pass
        loss = loss_fn(predictions, targets)    # 2. compute the loss
        optimizer.zero_grad()                   # 3. clear old gradients
        loss.backward()                         # 4. backpropagation
        optimizer.step()                        # 5. update the weights
```

Memorise this shape. Almost every model you will ever train, from a small classifier to a language model, uses it.

## Prepare the data

We will classify the breast cancer dataset (30 measurements per patient, benign or malignant). Neural networks need **scaled** inputs, and the scaler must learn only from training data:

```python
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

torch.manual_seed(0)
np.random.seed(0)

data = load_breast_cancer()
X_train, X_test, y_train, y_test = train_test_split(data.data, data.target, test_size=0.25, random_state=0, stratify=data.target)

scaler = StandardScaler().fit(X_train)                     # learn the scaling from training data only
X_train, X_test = scaler.transform(X_train), scaler.transform(X_test)

train_ds = TensorDataset(torch.tensor(X_train, dtype=torch.float32), torch.tensor(y_train, dtype=torch.float32))
test_ds = TensorDataset(torch.tensor(X_test, dtype=torch.float32), torch.tensor(y_test, dtype=torch.float32))

train_loader = DataLoader(train_ds, batch_size=32, shuffle=True)
test_loader = DataLoader(test_ds, batch_size=128)

print("training examples:", len(train_ds), " test examples:", len(test_ds))
print("batches per epoch:", len(train_loader))
xb, yb = next(iter(train_loader))
print("one batch:", tuple(xb.shape), tuple(yb.shape))
```

```output
training examples: 426  test examples: 143
batches per epoch: 14
one batch: (32, 30) (32,)
```

`TensorDataset` pairs inputs with labels. `DataLoader` cuts the data into **batches** and, with `shuffle=True`, reshuffles every epoch so the model does not see examples in the same order each time.

## Model, loss and optimiser

```python
model = nn.Sequential(
    nn.Linear(30, 16), nn.ReLU(),
    nn.Linear(16, 1),                       # one output: the logit for "benign"
)
loss_fn = nn.BCEWithLogitsLoss()            # binary cross-entropy, expects logits
optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

print(sum(p.numel() for p in model.parameters()), "parameters")
```

```output
513 parameters
```

**Adam** is a popular optimiser (a smarter version of gradient descent, covered in a later lesson). `model.parameters()` hands the optimiser every weight to update.

## Evaluation helper

```python
def evaluate(loader):
    model.eval()                                   # switch off dropout etc.
    total_loss, correct, count = 0.0, 0, 0
    with torch.no_grad():                          # no gradients needed
        for xb, yb in loader:
            logits = model(xb).squeeze(1)
            total_loss += loss_fn(logits, yb).item() * len(yb)
            correct += ((logits > 0).float() == yb).sum().item()      # logit > 0 means probability > 0.5
            count += len(yb)
    return total_loss / count, correct / count
```

A logit above 0 means a probability above 0.5, so we do not even need to apply the sigmoid to decide the class.

## Train it

```python
for epoch in range(1, 21):
    model.train()
    for xb, yb in train_loader:
        logits = model(xb).squeeze(1)
        loss = loss_fn(logits, yb)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    if epoch in (1, 2, 5, 10, 20):
        train_loss, train_acc = evaluate(train_loader)
        test_loss, test_acc = evaluate(test_loader)
        print(f"epoch {epoch:>2}: train loss {train_loss:.3f} acc {train_acc:.3f} | test loss {test_loss:.3f} acc {test_acc:.3f}")
```

```output
epoch  1: train loss 0.147 acc 0.948 | test loss 0.221 acc 0.916
epoch  2: train loss 0.078 acc 0.979 | test loss 0.130 acc 0.944
epoch  5: train loss 0.046 acc 0.991 | test loss 0.115 acc 0.958
epoch 10: train loss 0.031 acc 0.993 | test loss 0.122 acc 0.958
epoch 20: train loss 0.013 acc 0.995 | test loss 0.108 acc 0.958
```

Both losses fall quickly and accuracy rises: after just a few epochs the network is already very accurate. This is a healthy training run: both losses drop quickly in the first epochs. After that the test loss flattens at about 0.11 while the training loss keeps shrinking (0.013), so a small gap opens between them. That gap is the first hint of **overfitting**, the subject of an upcoming lesson.

## Reading the numbers

| What you see | What it means |
| --- | --- |
| train loss falling, test loss falling | learning well |
| train loss falling, test loss rising | **overfitting** (the next lessons) |
| both high and flat | underfitting or a learning rate problem |
| loss jumping around wildly | learning rate too high |
| loss is `nan` | exploding values: lower the learning rate, check the data for errors |

## Making predictions on new data

```python
model.eval()
with torch.no_grad():
    new_patients = torch.tensor(X_test[:5], dtype=torch.float32)
    probabilities = torch.sigmoid(model(new_patients).squeeze(1))

print("predicted probability of 'benign':", [round(p, 2) for p in probabilities.tolist()])
print("actual labels                    :", y_test[:5].tolist())
```

```output
predicted probability of 'benign': [1.0, 0.0, 0.0, 1.0, 0.0]
actual labels                    : [1, 0, 0, 1, 0]
```

For new data, apply the **same scaler** you fitted on the training data, then `model.eval()` and `no_grad`. Apply `sigmoid` here because we want probabilities for people to read.

## A reusable template

| Step | Code |
| --- | --- |
| 1. split the data, **then** scale | `train_test_split`, `StandardScaler().fit(train)` |
| 2. wrap in tensors and loaders | `TensorDataset`, `DataLoader(shuffle=True)` |
| 3. define model, loss, optimiser | `nn.Sequential`, `BCEWithLogitsLoss`, `Adam` |
| 4. loop: forward, loss, `zero_grad`, `backward`, `step` | the five lines |
| 5. evaluate each epoch with `eval()` and `no_grad` | track train and validation metrics |
| 6. keep the best model, test **once** at the end | avoid tuning on the test set |

:::tip
Always set `torch.manual_seed(...)` at the start while learning. Results then repeat from run to run, which makes it much easier to tell whether a change you made actually helped.
:::
