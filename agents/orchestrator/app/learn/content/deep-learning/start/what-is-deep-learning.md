---
title: What is deep learning?
summary: Understand what deep learning is, how it differs from machine learning, where it is used, and what you need to learn it.
takeaways:
- Deep learning uses neural networks with many layers that learn their own features from raw data
- It shines on images, sound, text and other unstructured data, and needs lots of data and computing power
- You will build one from scratch first, then use PyTorch, so nothing stays a mystery
---
## The big idea in one picture

Think about how you recognise a friend's face. Nobody gave you a rule such as "eyes are 6 cm apart". Your brain learned, from thousands of examples, to pick out simple things first (edges, colours), then shapes (an eye, a nose), then whole faces. Each step builds on the one before.

**Deep learning** does the same with software. A **neural network** is a stack of layers; early layers find simple patterns, later layers combine them into complex ones. The word "deep" just means **many layers**.

| | Traditional machine learning | Deep learning |
| --- | --- | --- |
| Who builds the features? | **you** (feature engineering) | the network learns them from raw data |
| Works best on | tables of numbers (sales, customers) | images, audio, text, video |
| Data needed | hundreds to thousands of rows | often tens of thousands to millions |
| Computing power | a laptop is fine | often needs a GPU |
| Easy to explain? | often yes (trees, linear models) | harder (a "black box") |

Deep learning is **part of** machine learning, which is part of artificial intelligence.

## Where it is used

| Area | Examples |
| --- | --- |
| **Vision** | face unlock, medical scans, self-driving cars, reading number plates |
| **Language** | translation, chatbots, summarising, ChatGPT-style assistants |
| **Speech** | voice assistants, call transcription |
| **Recommendations** | what to watch, what to buy |
| **Science** | protein structure, weather, drug discovery |
| **Generation** | images, music, code, video |

## What a network looks like

```py
input layer        hidden layers          output layer
 (your data)    (learn the patterns)     (the answer)

   x1 ──┐         ┌─ o ─┐
   x2 ──┼──────►  ├─ o ─┼──►  o  ──►  o ──► prediction
   x3 ──┘         └─ o ─┘
```

Each circle (a **neuron**) takes numbers in, mixes them using **weights**, and passes a number on. Training means finding good weights, by showing the network many examples and nudging the weights to reduce its mistakes.

## The four ideas the whole subject is built on

| Idea | Plain meaning |
| --- | --- |
| **Forward pass** | feed the input through the layers to get a prediction |
| **Loss** | one number saying how wrong the prediction is |
| **Backpropagation** | work out how much each weight contributed to the mistake |
| **Gradient descent** | nudge every weight a little in the direction that reduces the loss |

Repeat these four steps thousands of times and the network learns. Every lesson in this course is a closer look at one of them. A very small version in code, to see the loop:

```python
import numpy as np

# learn y = 2x + 1 from examples, using the same four ideas
x = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
y = 2 * x + 1

w, b = 0.0, 0.0                       # start knowing nothing
learning_rate = 0.05

for step in range(200):
    prediction = w * x + b                      # 1. forward pass
    loss = np.mean((prediction - y) ** 2)       # 2. loss
    grad_w = np.mean(2 * (prediction - y) * x)  # 3. gradients (backpropagation, in its simplest form)
    grad_b = np.mean(2 * (prediction - y))
    w -= learning_rate * grad_w                 # 4. gradient descent: nudge the weights
    b -= learning_rate * grad_b

print(round(w, 2), round(b, 2), round(loss, 6))
```

```output
2.0 1.0 0.0
```

The program was never told the rule. It started with `w = 0` and `b = 0` and **found** `w ≈ 2`, `b ≈ 1` by repeating the four steps. A real network does exactly this, with millions of weights instead of two.

## What you need

| Need | Notes |
| --- | --- |
| Python | comfortable with functions and loops |
| NumPy | arrays, shapes, matrix multiplication (the NumPy course) |
| Machine learning basics | train/test split, overfitting, metrics (the Machine Learning course) |
| School maths | basic algebra; the idea of a slope; we explain the rest as we go |
| A computer | a normal laptop is enough for this course; a GPU is optional |

## How this course is organised

| Part | What you will do |
| --- | --- |
| **Foundations** | build a neuron, a network and backpropagation **by hand in NumPy**, so you see inside |
| **PyTorch** | do the same with a professional library: tensors, models, training loops |
| **Training craft** | optimisers, overfitting, normalisation, and how to debug training |
| **Images** | convolutional neural networks and transfer learning |
| **Sequences and text** | RNNs, LSTMs, embeddings, attention and transformers |
| **Advanced** | autoencoders, large language models and fine-tuning, deployment, responsible AI |

:::tip
Do not just read. **Run every code block**, change a number, and see what breaks. Deep learning is learned by experimenting, and the experiments here run in seconds on a normal laptop.
:::

:::note
Training involves random starting weights, so your own numbers may differ slightly from the ones printed here (different library versions and computers give slightly different digits). The **pattern** (loss going down, accuracy going up) will be the same. We set random seeds so the examples are as repeatable as possible.
:::
