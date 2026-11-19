---
title: The artificial neuron
summary: Build a single neuron, see what it can and cannot do, and discover why we need layers by solving the famous XOR problem.
takeaways:
- A neuron computes a weighted sum of its inputs, adds a bias and applies an activation function
- A single neuron can only draw one straight line between classes
- Stacking neurons in layers lets a network solve problems no single neuron can, such as XOR
---
## One neuron

A neuron is a tiny calculator:

1. Multiply each input by its **weight** (how much that input matters).
2. Add them all up, and add a **bias** (a built-in nudge, like a threshold).
3. Pass the total through an **activation function** that decides the output.

In symbols: `output = activation(w1·x1 + w2·x2 + ... + bias)`.

```python
import numpy as np

def sigmoid(z):
    return 1 / (1 + np.exp(-z))

x = np.array([2.0, 3.0])          # two inputs
w = np.array([0.5, -0.2])         # one weight per input
b = 0.1                           # the bias

z = np.dot(w, x) + b              # the weighted sum: 0.5*2 + (-0.2)*3 + 0.1
print("weighted sum z =", round(z, 2))
print("output         =", round(float(sigmoid(z)), 4))
```

```output
weighted sum z = 0.5
output         = 0.6225
```

The weighted sum is 0.5 × 2 − 0.2 × 3 + 0.1 = 0.5. The **sigmoid** squashes any number into the range 0 to 1, so the neuron outputs about 0.62, which we can read as "62% sure".

## A neuron as a decision maker

With a **step** activation (output 1 if the sum is above zero, else 0), the neuron becomes a yes/no decider. Choosing the weights by hand, we can make it behave like logic gates:

```python
def neuron(x, w, b):
    return 1 if np.dot(w, x) + b > 0 else 0

inputs = [(0, 0), (0, 1), (1, 0), (1, 1)]

print("x1 x2 | AND OR")
for x1, x2 in inputs:
    x = np.array([x1, x2])
    and_out = neuron(x, np.array([1, 1]), -1.5)     # fires only when BOTH inputs are on
    or_out = neuron(x, np.array([1, 1]), -0.5)      # fires when AT LEAST ONE input is on
    print(f" {x1}  {x2} |  {and_out}   {or_out}")
```

```output
x1 x2 | AND OR
 0  0 |  0   0
 0  1 |  0   1
 1  0 |  0   1
 1  1 |  1   1
```

The same neuron structure became AND or OR just by changing the numbers. **Learning** is the process of finding those numbers automatically from examples, instead of choosing them by hand.

## What a single neuron really does: a straight line

With two inputs, `w1·x1 + w2·x2 + b = 0` is the equation of a **straight line**. The neuron says "yes" on one side of the line and "no" on the other. So a single neuron can only separate classes that a **straight line can separate**.

| Problem | Can one neuron solve it? |
| --- | --- |
| AND, OR | yes: one line separates the 1s from the 0s |
| spam versus not spam, if one line splits them | yes |
| **XOR** (true when the inputs **differ**) | **no** |

## The XOR problem

XOR gives 1 for (0,1) and (1,0), and 0 for (0,0) and (1,1). Put the four points on paper: the two 1s are on opposite corners, and so are the two 0s. **No single straight line** can put both 1s on one side and both 0s on the other. This simple fact stopped neural network research for years, until people realised the fix: use **more than one layer**.

## Two layers solve it

Use two hidden neurons, then one output neuron that combines them:

- hidden neuron A: OR (at least one input on)
- hidden neuron B: NAND (not both inputs on)
- output: AND of A and B, which means "at least one is on, but not both" = XOR

```python
def layer_network(x1, x2):
    x = np.array([x1, x2])
    a = neuron(x, np.array([1, 1]), -0.5)          # OR
    b = neuron(x, np.array([-1, -1]), 1.5)         # NAND
    return neuron(np.array([a, b]), np.array([1, 1]), -1.5)     # AND of the two hidden neurons

print("x1 x2 | XOR")
for x1, x2 in inputs:
    print(f" {x1}  {x2} |  {layer_network(x1, x2)}")
```

```output
x1 x2 | XOR
 0  0 |  0
 0  1 |  1
 1  0 |  1
 1  1 |  0
```

The network gets all four rows right. The hidden layer **re-describes** the inputs in a new way (using OR and NAND) that makes the problem solvable by a straight line in the next layer. This is the secret of deep learning: **each layer transforms the data into a representation that makes the next layer's job easier**.

:::remember
One neuron draws one straight line. Layers of neurons, with a non-linear activation between them, can bend and combine lines to draw any shape. That is why deep networks can learn faces, speech and language.
:::

:::interview
**Interviewers often ask:** "Why can't a single perceptron solve XOR?" Because XOR is not linearly separable: no single straight line separates its two classes. A network with a hidden layer and a non-linear activation can, because the hidden layer maps the inputs into a space where they are separable.
:::
