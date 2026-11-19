---
title: Layers and the forward pass
summary: Stack neurons into layers, write the whole forward pass as matrix multiplications, and learn to read shapes and count parameters.
takeaways:
- A layer is many neurons side by side, computed together as one matrix multiplication
- Shapes are the language of deep learning: (samples, features) times (features, neurons)
- Parameters are the weights and biases; they are what training changes
---
## From one neuron to a layer

A **layer** is many neurons that all look at the same inputs, each with its own weights. Instead of looping over neurons, we put all their weights into **one matrix** and let matrix multiplication do the work.

If a layer has 3 inputs and 4 neurons:

| Object | Shape | Meaning |
| --- | --- | --- |
| input `X` | (samples, 3) | one row per example, 3 features each |
| weights `W` | (3, 4) | one column per neuron |
| bias `b` | (4,) | one number per neuron |
| output `X @ W + b` | (samples, 4) | 4 numbers per example, one per neuron |

The rule to remember: **the inner sizes must match** (3 and 3), and the **outer sizes** give the result (samples, 4).

## A two-layer network, forward pass

```python
import numpy as np

rng = np.random.default_rng(0)

X = rng.normal(size=(5, 3))            # 5 examples, 3 features each

W1 = rng.normal(size=(3, 4)) * 0.5     # layer 1: 3 inputs -> 4 hidden neurons
b1 = np.zeros(4)
W2 = rng.normal(size=(4, 1)) * 0.5     # layer 2: 4 hidden -> 1 output
b2 = np.zeros(1)

def relu(z):
    return np.maximum(0, z)

def sigmoid(z):
    return 1 / (1 + np.exp(-z))

hidden_input = X @ W1 + b1
hidden = relu(hidden_input)
output = sigmoid(hidden @ W2 + b2)

print("X        :", X.shape)
print("hidden   :", hidden.shape)
print("output   :", output.shape)
print("outputs  :", np.round(output.ravel(), 3))
print("all outputs between 0 and 1:", bool(((output > 0) & (output < 1)).all()))
```

```output
X        : (5, 3)
hidden   : (5, 4)
output   : (5, 1)
outputs  : [0.485 0.482 0.484 0.46  0.433]
all outputs between 0 and 1: True
```

Five examples went in; five probabilities came out (one per example). The numbers are meaningless right now, because the weights are random. Training will turn them into useful ones.

## Counting parameters

The **parameters** of a network are all its weights and biases: the numbers training adjusts.

```python
n_params = W1.size + b1.size + W2.size + b2.size
print("layer 1:", W1.size, "weights +", b1.size, "biases")
print("layer 2:", W2.size, "weights +", b2.size, "biases")
print("total parameters:", n_params)
```

```output
layer 1: 12 weights + 4 biases
layer 2: 4 weights + 1 biases
total parameters: 21
```

A layer going from `n_in` inputs to `n_out` neurons has `n_in × n_out + n_out` parameters. A network for 28 by 28 pixel images with 128 hidden neurons already has about 100,000. GPT-style language models have **billions**.

## Names you will hear

| Term | Meaning |
| --- | --- |
| **input layer** | the data itself (it holds no weights) |
| **hidden layers** | the layers in between; they learn the patterns |
| **output layer** | produces the answer (a probability, a number, class scores) |
| **dense / fully connected / linear layer** | every input connects to every neuron (what we just built) |
| **depth** | the number of layers |
| **width** | the number of neurons in a layer |
| **architecture** | the design: how many layers, of what kind and size |
| **hyperparameter** | a setting you choose (layers, width, learning rate); not learned |

## Batches and why shapes matter

Real data comes in **batches**: groups of examples processed together, which is much faster on modern hardware. The first number in the shape is always the **batch size**, and it can change without altering the network.

```python
for batch_size in (1, 32, 1000):
    batch = rng.normal(size=(batch_size, 3))
    out = sigmoid(relu(batch @ W1 + b1) @ W2 + b2)
    print(f"batch of {batch_size:>4} -> output shape {out.shape}")
```

```output
batch of    1 -> output shape (1, 1)
batch of   32 -> output shape (32, 1)
batch of 1000 -> output shape (1000, 1)
```

The same weights handle any batch size. When something goes wrong in deep learning, the cause is very often **a shape that is not what you thought**, so printing shapes is the first debugging step.

:::warning
The classic error message is "shapes cannot be multiplied" (for example `(5,3) @ (4,1)`). Check that the **last** dimension of the left array equals the **first** dimension of the right one.
:::
