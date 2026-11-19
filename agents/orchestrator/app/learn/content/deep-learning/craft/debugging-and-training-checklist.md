---
title: Debugging and a training checklist
summary: Find out why a model will not learn: the overfit-one-batch test, the classic bugs, and a step-by-step checklist used by practitioners.
takeaways:
- Deep learning bugs are usually silent: the code runs and the model is quietly wrong
- Overfitting one tiny batch is the best first test of a model and training loop
- Check shapes, labels, learning rate and the loss function before blaming the architecture
---
## Silent bugs

In ordinary programming a bug usually causes an error message. In deep learning, a bug usually causes **nothing**: the code runs, the loss moves a little, and the model is simply bad. This lesson gives you a method to find the cause.

## Test 1: can it overfit one small batch?

A correct model with a correct training loop must be able to **memorise** 16 examples. If it cannot, there is a bug (or the learning rate is far off).

```python
import torch
from torch import nn
from sklearn.datasets import load_breast_cancer
from sklearn.preprocessing import StandardScaler

torch.manual_seed(0)
X, y = load_breast_cancer(return_X_y=True)
X = StandardScaler().fit_transform(X)
xb = torch.tensor(X[:16], dtype=torch.float32)
yb = torch.tensor(y[:16], dtype=torch.float32)

model = nn.Sequential(nn.Linear(30, 32), nn.ReLU(), nn.Linear(32, 1))
optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
loss_fn = nn.BCEWithLogitsLoss()

for step in range(1, 101):
    logits = model(xb).squeeze(1)
    loss = loss_fn(logits, yb)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    if step in (1, 10, 50, 100):
        accuracy = ((logits > 0).float() == yb).float().mean().item()
        print(f"step {step:>3}: loss {loss.item():.4f}   accuracy {accuracy:.2f}")
```

```output
step   1: loss 0.6292   accuracy 0.75
step  10: loss 0.0537   accuracy 1.00
step  50: loss 0.0002   accuracy 1.00
step 100: loss 0.0001   accuracy 1.00
```

The loss collapses towards zero and accuracy reaches 100%. **This is the result you want.** Had it stayed stuck, the culprit would be in the model, the loss, the labels or the training loop, not in "needing more data". Only after this test passes should you train on the full dataset.

## Classic bug 1: softmax before CrossEntropyLoss

`nn.CrossEntropyLoss` applies the softmax itself. If your model already applies it, the loss is computed on the wrong thing:

```python
logits = torch.tensor([[5.0, 0.0, 0.0]])
target = torch.tensor([0])

correct = nn.CrossEntropyLoss()(logits, target)
mistaken = nn.CrossEntropyLoss()(torch.softmax(logits, dim=1), target)      # softmax applied twice
print("correct loss (raw logits)       :", round(correct.item(), 4))
print("mistaken loss (softmax then CE) :", round(mistaken.item(), 4))
```

```output
correct loss (raw logits)       : 0.0134
mistaken loss (softmax then CE) : 0.5599
```

The model is very confident and right, so the correct loss is nearly zero. The mistaken version reports a much larger loss and squashes the gradients, so training is slow and weak. No error is raised.

## Classic bug 2: silent broadcasting in the loss

```python
import warnings
predictions = torch.tensor([[1.0], [2.0], [3.0]])          # shape (3, 1)
targets = torch.tensor([1.0, 2.0, 3.0])                    # shape (3,)  perfect predictions!

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    wrong = nn.functional.mse_loss(predictions, targets)               # broadcasts to a 3 x 3 comparison
right = nn.functional.mse_loss(predictions.squeeze(1), targets)
print("loss with mismatched shapes:", round(wrong.item(), 3), "(should be 0 for perfect predictions)")
print("loss with matching shapes  :", round(right.item(), 3))
```

```output
loss with mismatched shapes: 1.333 (should be 0 for perfect predictions)
loss with matching shapes  : 0.0
```

The predictions are perfect, yet the first loss is not zero: PyTorch silently compared every prediction with every target. The model would train toward the average and learn nothing useful. **Always make sure predictions and targets have the same shape.**

## Classic bug 3: the list of mistakes

| Bug | Symptom | Check |
| --- | --- | --- |
| forgot `optimizer.zero_grad()` | gradients pile up, training explodes or is erratic | the five-line loop |
| forgot `model.eval()` when testing | noisy, worse test scores (dropout still on) | `eval()` and `no_grad` in your test function |
| learning rate wrong | loss flat (too small) or `nan` and jumping (too large) | try 10x smaller and 10x larger |
| inputs not scaled | slow or stuck training | print `X.mean()` and `X.std()` |
| labels wrong or shuffled apart from inputs | accuracy at chance level | look at a few raw examples with their labels |
| wrong loss or double softmax/sigmoid | loss values that make no sense | read the loss function's expected input |
| wrong dtype (`int` labels for BCE, `float` for CE classes) | an error, or a silent wrong loss | print `dtype` of inputs and targets |
| data leakage between train and test | unbelievably good test score | split first; fit scalers on training data only |
| test set used for decisions | optimistic final score | use a validation set |
| forgot to move data or model to the GPU | a device mismatch error | `.to(device)` on both |

## A systematic checklist

1. **Look at the data.** Print or plot a few inputs with their labels. Check ranges, missing values and class balance.
2. **Start simple.** A small model, a standard loss, Adam at `1e-3`. Get something working before improving it.
3. **Check shapes** at every step: input, model output, target.
4. **Check the first loss.** For a balanced two-class problem it should be near `ln 2 = 0.69`; for `k` classes near `ln k`. A very different first value means something is wrong.
5. **Overfit one batch** (above). Must reach near-zero loss.
6. **Train on the full training set** and plot **training and validation** loss.
7. **Diagnose using the curves:** both high means underfitting (bigger model, train longer, higher learning rate); big gap means overfitting (the previous lesson).
8. **Change one thing at a time** and record the result.

```python
import math
print("expected starting loss, 2 balanced classes :", round(math.log(2), 3))
print("expected starting loss, 10 classes         :", round(math.log(10), 3))
```

```output
expected starting loss, 2 balanced classes : 0.693
expected starting loss, 10 classes         : 2.303
```

This quick check from step 4 caught more bugs than any tool: if a 10-class model starts at a loss of 20 instead of about 2.3, the output scaling or loss is wrong.

## A simple learning-rate range test

Try a range of learning rates for a short run and look for the region where the loss falls fastest:

```python
def short_run(lr, steps=60):
    torch.manual_seed(0)
    net = nn.Sequential(nn.Linear(30, 32), nn.ReLU(), nn.Linear(32, 1))
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    for _ in range(steps):
        loss = loss_fn(net(xb).squeeze(1), yb)
        opt.zero_grad()
        loss.backward()
        opt.step()
    return loss.item()

for lr in (1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1.0):
    print(f"lr {lr:>7}: loss after 60 steps {short_run(lr):.4f}")
```

```output
lr   1e-05: loss after 60 steps 0.6186
lr  0.0001: loss after 60 steps 0.5328
lr   0.001: loss after 60 steps 0.1192
lr    0.01: loss after 60 steps 0.0002
lr     0.1: loss after 60 steps 0.0000
lr     1.0: loss after 60 steps 0.0000
```

Rates of 0.00001 and 0.0001 are clearly too slow (the loss has barely moved after 60 steps), and from 0.01 upwards the loss reaches almost zero. This tiny batch is very forgiving, so even a rate of 1.0 succeeds here; on real data the upper limit appears much earlier (in the optimiser lesson, 1.0 broke a real training run). Use this test to find the **too-slow** side confidently, and choose a value comfortably **below** the point where training starts to become unstable.

:::tip
Keep a small notebook (or use a tool like **TensorBoard** or **Weights & Biases**) recording each experiment: what you changed, and the training and validation curves. Without records, you cannot tell which change helped.
:::
