---
title: Loss functions
summary: Measure how wrong a network is with mean squared error and cross-entropy, and see why the choice of loss matters.
takeaways:
- The loss is one number that says how wrong the predictions are; training tries to make it small
- Use MSE for numbers and cross-entropy for classes
- Cross-entropy punishes confident wrong answers very heavily
---
## What is a loss?

Training needs a **score for being wrong**, so it knows which way to move the weights. That score is the **loss** (also called the cost or error). Low loss means good predictions. The network does not try to maximise accuracy directly, because accuracy is a bumpy, step-like number with no useful slope; the loss is **smooth**, so we can follow its slope downhill.

## Mean squared error (for predicting numbers)

Take the difference between each prediction and the truth, square it, and average:

```python
import numpy as np

y_true = np.array([3.0, 5.0, 8.0])
y_pred = np.array([2.5, 5.5, 6.0])

errors = y_pred - y_true
mse = np.mean(errors ** 2)
print("errors:", errors)
print("MSE   :", round(float(mse), 3))
```

```output
errors: [-0.5  0.5 -2. ]
MSE   : 1.5
```

Squaring has two effects: negative and positive errors cannot cancel, and **big errors count much more** than small ones. The error of 2.0 contributes 4.0, while the two errors of 0.5 contribute only 0.25 each.

## Cross-entropy (for classes)

For classification the network outputs probabilities, and we want a high probability for the **correct** class. **Cross-entropy** is simply `−log(probability given to the correct answer)`:

```python
for p in (0.99, 0.9, 0.5, 0.1, 0.01):
    print(f"probability given to the right answer {p:>5}  ->  loss {-np.log(p):.3f}")
```

```output
probability given to the right answer  0.99  ->  loss 0.010
probability given to the right answer   0.9  ->  loss 0.105
probability given to the right answer   0.5  ->  loss 0.693
probability given to the right answer   0.1  ->  loss 2.303
probability given to the right answer  0.01  ->  loss 4.605
```

Look at how it behaves: a confident correct answer (0.99) costs almost nothing; a coin-flip (0.5) costs a moderate amount; and a confident **wrong** answer (giving the right class only 0.01) costs a huge amount, more than 4.6. This steep penalty pushes the network hard away from being confidently wrong.

## Binary cross-entropy (two classes)

When the answer is yes (1) or no (0) and the network gives a probability `p` of yes:

`loss = −[ y · log(p) + (1 − y) · log(1 − p) ]`

```python
def binary_cross_entropy(y, p):
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))

print("true = 1, predicted 0.9 :", round(float(binary_cross_entropy(1, 0.9)), 3))
print("true = 1, predicted 0.1 :", round(float(binary_cross_entropy(1, 0.1)), 3))
print("true = 0, predicted 0.1 :", round(float(binary_cross_entropy(0, 0.1)), 3))
print("true = 0, predicted 0.9 :", round(float(binary_cross_entropy(0, 0.9)), 3))
```

```output
true = 1, predicted 0.9 : 0.105
true = 1, predicted 0.1 : 2.303
true = 0, predicted 0.1 : 0.105
true = 0, predicted 0.9 : 2.303
```

Whichever way it is wrong, a confident mistake is expensive, and a confident correct answer is cheap.

## Multi-class cross-entropy with softmax

With logits for three classes and the correct class being class 0:

```python
import torch
import torch.nn.functional as F

logits = np.array([2.0, 1.0, 0.1])
probs = np.exp(logits - logits.max()) / np.exp(logits - logits.max()).sum()
by_hand = -np.log(probs[0])                                   # probability of the correct class

by_torch = F.cross_entropy(torch.tensor([logits]), torch.tensor([0]))       # takes LOGITS, applies softmax itself

print("by hand :", round(float(by_hand), 4))
print("PyTorch :", round(float(by_torch), 4))
```

```output
by hand : 0.417
PyTorch : 0.417
```

Same answer. Note the important detail: PyTorch's `cross_entropy` expects the **raw logits**, not probabilities. It applies the softmax internally (in a numerically safer way). Applying softmax yourself first is a common mistake that we will demonstrate later.

## Choosing the loss

| Task | Loss | PyTorch |
| --- | --- | --- |
| predict a number | mean squared error (or MAE when outliers matter) | `nn.MSELoss()`, `nn.L1Loss()` |
| yes or no | binary cross-entropy | `nn.BCEWithLogitsLoss()` |
| one of many classes | cross-entropy | `nn.CrossEntropyLoss()` |
| several tags at once | binary cross-entropy per tag | `nn.BCEWithLogitsLoss()` |
| ranking, similarity, generation | specialised losses (triplet, contrastive, KL divergence) | many options |

`BCEWithLogitsLoss` and `CrossEntropyLoss` both take **logits** (no sigmoid or softmax in the model's last layer during training). They combine the activation and the loss in one stable calculation.

## Loss versus metric

| | Loss | Metric |
| --- | --- | --- |
| Purpose | what training **minimises** | what **you** care about |
| Must be | smooth (has a slope) | easy to understand |
| Example | cross-entropy | accuracy, F1, RMSE |

They usually move together, but not always. Watch both: the loss tells you the network is learning, and the metric tells you whether it is useful.

:::interview
**Interviewers often ask:** "Why cross-entropy instead of MSE for classification?" Cross-entropy matches the probabilistic view (maximum likelihood), gives large gradients when the model is confidently wrong so it learns quickly, while MSE on probabilities gives tiny gradients when a sigmoid or softmax saturates, slowing learning.
:::
