---
title: Activation functions
summary: Understand why networks need non-linear activations, meet sigmoid, tanh, ReLU and softmax, and learn when to use each.
takeaways:
- Without a non-linear activation, any number of layers collapses into a single linear layer
- ReLU is the default for hidden layers; sigmoid and softmax belong at the output for probabilities
- Softmax turns a list of scores into probabilities that add up to 1
---
## Why we need activations

Suppose every layer only did `X @ W + b`, with no activation. Two such layers can be **merged into one** layer, because multiplying matrices gives another matrix. Stacking a hundred layers would give no more power than one. The **non-linear activation** between layers is what lets a deep network learn curved, complicated patterns.

See the collapse for yourself:

```python
import numpy as np

rng = np.random.default_rng(1)
X = rng.normal(size=(4, 3))
W1 = rng.normal(size=(3, 5))
W2 = rng.normal(size=(5, 2))

two_linear_layers = (X @ W1) @ W2
one_merged_layer = X @ (W1 @ W2)
print("two linear layers equal one merged layer:", np.allclose(two_linear_layers, one_merged_layer))

relu = lambda z: np.maximum(0, z)
with_relu = relu(X @ W1) @ W2
print("with a ReLU in between, they are different:", not np.allclose(with_relu, one_merged_layer))
```

```output
two linear layers equal one merged layer: True
with a ReLU in between, they are different: True
```

## The common activation functions

```python
def sigmoid(z):
    return 1 / (1 + np.exp(-z))

z = np.array([-4.0, -2.0, 0.0, 2.0, 4.0])
print("z          ", z)
print("sigmoid    ", np.round(sigmoid(z), 3))
print("tanh       ", np.round(np.tanh(z), 3))
print("relu       ", np.maximum(0, z))
print("leaky relu ", np.where(z > 0, z, 0.01 * z))
```

```output
z           [-4. -2.  0.  2.  4.]
sigmoid     [0.018 0.119 0.5   0.881 0.982]
tanh        [-0.999 -0.964  0.     0.964  0.999]
relu        [0. 0. 0. 2. 4.]
leaky relu  [-0.04 -0.02  0.    2.    4.  ]
```

| Function | Formula | Output range | Used for |
| --- | --- | --- | --- |
| **Sigmoid** | 1 / (1 + e^−z) | 0 to 1 | the output of a yes/no (binary) problem |
| **Tanh** | (e^z − e^−z) / (e^z + e^−z) | −1 to 1 | older networks, some recurrent layers |
| **ReLU** | max(0, z) | 0 to ∞ | **the default for hidden layers** |
| **Leaky ReLU** | z if z > 0, else 0.01 z | −∞ to ∞ | when ReLU neurons "die" |
| **GELU / SiLU** | smooth versions of ReLU | about −0.2 to ∞ | transformers and modern networks |
| **Softmax** | e^zᵢ / Σ e^zⱼ | 0 to 1, sum 1 | the output of a multi-class problem |

## Why ReLU became the default

- It is **very cheap**: just "keep positive, zero the negatives".
- It does not **saturate** for positive values: sigmoid and tanh flatten out for large inputs, so their gradients become almost zero and learning stalls (the "vanishing gradient", covered later).
- It works well in practice.

Its one weakness: a neuron whose input is always negative outputs 0 forever, with zero gradient, and stops learning (a **dead ReLU**). Leaky ReLU avoids this by keeping a small slope for negatives.

## Softmax: scores to probabilities

For a problem with several classes (cat, dog, bird), the final layer outputs raw scores called **logits**. Softmax turns them into probabilities:

```python
def softmax(logits):
    shifted = logits - np.max(logits)           # subtract the max: avoids overflow, same result
    exp = np.exp(shifted)
    return exp / exp.sum()

logits = np.array([2.0, 1.0, 0.1])
probs = softmax(logits)
print("probabilities:", np.round(probs, 3))
print("sum          :", round(float(probs.sum()), 3))
print("predicted class:", int(np.argmax(probs)))
```

```output
probabilities: [0.659 0.242 0.099]
sum          : 1.0
predicted class: 0
```

The biggest score gets the biggest share, all the probabilities are positive, and they add up to 1. The "subtract the max" line matters: without it, `np.exp(1000)` overflows to infinity. Real libraries do this for you.

## Choosing the output activation

| Your task | Output layer | Loss (next lesson) |
| --- | --- | --- |
| predict a number (price, temperature) | **none** (linear output) | mean squared error |
| yes or no | **sigmoid**, one neuron | binary cross-entropy |
| one of many classes | **softmax**, one neuron per class | cross-entropy |
| several labels at once (tags) | **sigmoid**, one neuron per label | binary cross-entropy |

:::tip
Hidden layers: start with **ReLU** (or GELU in transformers). Output layer: choose by the task, using the table above. That one rule covers most networks you will ever build.
:::

:::interview
**Interviewers often ask:** "Why do we use non-linear activation functions?" Without them, a stack of linear layers is equivalent to one linear layer and can only model linear relationships; non-linearity lets the network approximate complex functions. "Why ReLU instead of sigmoid in hidden layers?" It is cheap, does not saturate for positive inputs (reducing vanishing gradients) and trains faster, though it can suffer from dead neurons.
:::
