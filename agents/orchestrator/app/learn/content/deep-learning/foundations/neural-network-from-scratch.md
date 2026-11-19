---
title: A neural network from scratch
summary: Put it all together: build, train and test a complete neural network using only NumPy, so you understand every line a library normally hides.
takeaways:
- A complete network needs only a forward pass, a loss, a backward pass and an update
- The loss should fall steadily; if it does not, something is wrong
- Doing it once by hand makes frameworks like PyTorch much easier to trust
---
## The problem

We will classify points into two curved, interlocking half-moons. A straight line cannot separate them, so a single neuron fails, but a small network with one hidden layer can.

```python
import numpy as np
from sklearn.datasets import make_moons
from sklearn.model_selection import train_test_split

X, y = make_moons(n_samples=400, noise=0.2, random_state=0)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=0, stratify=y)
y_train_col = y_train.reshape(-1, 1)

print("training points:", X_train.shape, " test points:", X_test.shape)
print("classes in training data:", np.bincount(y_train))
```

```output
training points: (300, 2)  test points: (100, 2)
classes in training data: [150 150]
```

## The network

Two inputs, one hidden layer of 8 neurons with **tanh**, and one output neuron with a **sigmoid**. The loss is binary cross-entropy.

```python
rng = np.random.default_rng(0)

n_hidden = 8
W1 = rng.normal(0, 0.5, size=(2, n_hidden))
b1 = np.zeros((1, n_hidden))
W2 = rng.normal(0, 0.5, size=(n_hidden, 1))
b2 = np.zeros((1, 1))

def sigmoid(z):
    return 1 / (1 + np.exp(-z))

def forward(X):
    z1 = X @ W1 + b1
    h = np.tanh(z1)
    p = sigmoid(h @ W2 + b2)
    return h, p

def bce(y, p):
    p = np.clip(p, 1e-9, 1 - 1e-9)              # avoid log(0)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))

_, p0 = forward(X_train)
print("loss before training:", round(bce(y_train_col, p0), 3))
print("accuracy before training:", round(float(((p0 > 0.5).astype(int).ravel() == y_train).mean()), 3))
```

```output
loss before training: 0.708
accuracy before training: 0.42
```

Before training the loss is high and the accuracy is near chance, because the weights are random.

## The training loop

The backward pass is the chain rule from the last lesson, written in matrix form. For a sigmoid output with cross-entropy loss, the gradient at the output simplifies to `p − y`:

```python
learning_rate = 0.5
n = len(X_train)

for epoch in range(1, 1501):
    # forward pass
    h, p = forward(X_train)

    # backward pass
    dz2 = (p - y_train_col) / n                  # gradient at the output
    dW2 = h.T @ dz2
    db2 = dz2.sum(axis=0, keepdims=True)
    dh = dz2 @ W2.T
    dz1 = dh * (1 - h ** 2)                      # derivative of tanh is 1 - tanh^2
    dW1 = X_train.T @ dz1
    db1 = dz1.sum(axis=0, keepdims=True)

    # gradient descent update
    W1 -= learning_rate * dW1
    b1 -= learning_rate * db1
    W2 -= learning_rate * dW2
    b2 -= learning_rate * db2

    if epoch in (1, 10, 100, 500, 1500):
        print(f"epoch {epoch:>4}: loss {bce(y_train_col, p):.3f}")
```

```output
epoch    1: loss 0.708
epoch   10: loss 0.395
epoch  100: loss 0.322
epoch  500: loss 0.268
epoch 1500: loss 0.106
```

The loss falls fast at first (0.71 to 0.39 in just ten epochs), then improves slowly for a while, and then drops again (to 0.11) as the hidden neurons settle on the curved boundary. Such plateaus are normal. What matters is that the loss keeps going down.

## Does it generalise?

The test points were never used for learning:

```python
_, p_train = forward(X_train)
_, p_test = forward(X_test)
train_acc = ((p_train > 0.5).astype(int).ravel() == y_train).mean()
test_acc = ((p_test > 0.5).astype(int).ravel() == y_test).mean()
print("training accuracy:", round(float(train_acc), 3))
print("test accuracy    :", round(float(test_acc), 3))
```

```output
training accuracy: 0.963
test accuracy    : 0.96
```

High accuracy on both: the network learned the curved boundary from data, without anyone describing the moon shapes. A single neuron (logistic regression) is limited to a straight line, so it does worse, as the next comparison shows.

## Seeing what the hidden layer did

```python
logistic_like = np.mean(((forward(X_test)[1] > 0.5).astype(int).ravel() == y_test))
from sklearn.linear_model import LogisticRegression
line = LogisticRegression().fit(X_train, y_train)
print("straight-line model test accuracy:", round(float(line.score(X_test, y_test)), 3))
print("our small network test accuracy   :", round(float(logistic_like), 3))
```

```output
straight-line model test accuracy: 0.93
our small network test accuracy   : 0.96
```

The network beats the straight line (0.96 against 0.93) because its hidden neurons **bend** the decision boundary. The gap is modest on this gentle example; it grows quickly for data with more twisted shapes.

## What you just built

| Piece | In the code |
| --- | --- |
| parameters | `W1, b1, W2, b2` |
| forward pass | `forward(X)` |
| loss | `bce(y, p)` |
| backward pass | the `dz2, dW2, dh, dz1, dW1` lines (the chain rule) |
| optimiser | `W -= learning_rate * dW` (plain gradient descent) |
| training loop | the `for epoch` loop |

Every deep learning framework, however large, does these same things. PyTorch simply computes the backward pass **automatically** for any network, and runs it fast on GPUs.

## Experiments to try

| Change | What we measured (test accuracy) |
| --- | --- |
| `n_hidden = 1` | 0.93: one hidden neuron can only make a straight boundary, the same as logistic regression |
| `n_hidden = 8` (what we used) | 0.96 |
| `n_hidden = 32` | 0.98: more neurons fit the curve more closely |
| `learning_rate = 0.001` | 0.83: it learns, but so slowly that after 1,500 epochs the loss is still 0.52 |
| `learning_rate = 5` | 0.98: this problem is forgiving, and a big rate still works here. Do not assume that on harder problems (the earlier lesson showed a rate that diverges) |
| `noise=0.5` in `make_moons` | 0.86: the classes overlap, so accuracy cannot approach 100% |

:::tip
When you write a network by hand, check your gradients against a tiny numerical estimate (nudge a weight by 0.0001 and see how the loss changes). It is called **gradient checking** and catches most backpropagation bugs. Frameworks make this unnecessary day to day, which is exactly why understanding it once is valuable.
:::
