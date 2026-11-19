---
title: Sequences: RNNs and LSTMs
summary: Learn how recurrent networks read sequences step by step, build an RNN by hand, and train an LSTM that remembers information over many steps.
takeaways:
- A recurrent network keeps a hidden state that carries a memory of what it has read so far
- Plain RNNs forget over long sequences; LSTM and GRU cells use gates to remember
- Input shape for sequences is (batch, time steps, features)
---
## Data that comes in order

Some data is a **sequence**, where order matters: words in a sentence, notes in a song, daily prices, sensor readings. A dense network sees all inputs at once and has no notion of "before" and "after", and sequences have varying lengths. A **recurrent neural network (RNN)** reads one step at a time and keeps a **memory** (the **hidden state**) of what it has seen.

At each step `t`: `h_t = tanh( W · x_t + U · h_(t-1) + b )`. The new memory is a mix of the new input and the old memory.

## An RNN cell by hand

```python
import numpy as np
import torch
from torch import nn

torch.manual_seed(0)
rnn = nn.RNN(input_size=3, hidden_size=4, batch_first=True, nonlinearity="tanh")

x = torch.randn(2, 5, 3)                       # batch of 2 sequences, 5 time steps, 3 features each
output, h_last = rnn(x)
print("input  :", tuple(x.shape), "(batch, time, features)")
print("output :", tuple(output.shape), "(the hidden state at every step)")
print("h_last :", tuple(h_last.shape), "(final hidden state)")

# the same computation written by hand, using the layer's own weights
W, U = rnn.weight_ih_l0.detach().numpy(), rnn.weight_hh_l0.detach().numpy()
b = (rnn.bias_ih_l0 + rnn.bias_hh_l0).detach().numpy()
h = np.zeros((2, 4))
for t in range(5):
    h = np.tanh(x[:, t, :].numpy() @ W.T + h @ U.T + b)
print("hand-written loop matches nn.RNN:", np.allclose(h, h_last[0].detach().numpy(), atol=1e-5))
```

```output
input  : (2, 5, 3) (batch, time, features)
output : (2, 5, 4) (the hidden state at every step)
h_last : (1, 2, 4) (final hidden state)
hand-written loop matches nn.RNN: True
```

Inside, the RNN is just a loop that applies the same small formula at every time step, carrying `h` forward. The **same weights** are used at every step, which is why one RNN can read sequences of any length.

## The forgetting problem

A plain RNN has a vanishing-gradient problem across **time**: the gradient from the last step must travel back through every earlier step, multiplying small numbers again and again. So the network struggles to learn that something at step 1 matters at step 50. It effectively has a short memory.

## LSTM and GRU: memory with gates

**LSTM (Long Short-Term Memory)** adds a separate **cell state**, a conveyor belt of information, and three learned **gates** (numbers between 0 and 1) that control it:

| Gate | Question it answers |
| --- | --- |
| **forget gate** | how much of the old memory should I keep? |
| **input gate** | how much of the new information should I write? |
| **output gate** | how much of the memory should I reveal right now? |

Because the cell state can pass through many steps almost unchanged, gradients flow much further back in time. **GRU** is a simpler cousin with two gates and fewer parameters, which often performs just as well.

## A task that needs memory

A sequence of 15 random numbers between −1 and 1. The label is **1 if the very first number is positive**, otherwise 0. To answer at the end, the network must remember the first step for 14 steps.

```python
import torch
from torch import nn

def make_batch(n, length=15):
    x = torch.rand(n, length, 1) * 2 - 1
    y = (x[:, 0, 0] > 0).float()
    return x, y

class SequenceClassifier(nn.Module):
    def __init__(self, hidden=16, remember_bias=False):
        super().__init__()
        self.lstm = nn.LSTM(input_size=1, hidden_size=hidden, batch_first=True)
        self.head = nn.Linear(hidden, 1)
        if remember_bias:
            for name, parameter in self.lstm.named_parameters():
                if "bias" in name:
                    parameter.data[hidden:2 * hidden] = 1.0          # the forget-gate part of the bias

    def forward(self, x):
        output, (h_last, c_last) = self.lstm(x)
        return self.head(h_last[-1]).squeeze(1)          # use the final hidden state to decide

def train(remember_bias, steps=300, seed=0):
    torch.manual_seed(seed)
    model = SequenceClassifier(remember_bias=remember_bias)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    loss_fn = nn.BCEWithLogitsLoss()
    x_test, y_test = make_batch(500)
    for step in range(1, steps + 1):
        x, y = make_batch(64)
        loss = loss_fn(model(x), y)
        optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)      # clipping keeps recurrent training stable
        optimizer.step()
        if step in (50, 100, 200, 300):
            with torch.no_grad():
                accuracy = ((model(x_test) > 0).float() == y_test).float().mean().item()
            print(f"  step {step:>3}: loss {loss.item():.3f}   test accuracy {accuracy:.2f}")

print("standard LSTM:")
train(remember_bias=False)
```

```output
standard LSTM:
  step  50: loss 0.694   test accuracy 0.47
  step 100: loss 0.694   test accuracy 0.52
  step 200: loss 0.694   test accuracy 0.52
  step 300: loss 0.695   test accuracy 0.51
```

Surprise: **nothing is learned**. The accuracy stays at about 0.5, which is a coin flip. An LSTM is *able* to remember, but gradient descent has to **discover** how, and with the default starting weights the signal from step 1 has all but faded by step 15. This is a realistic lesson: a model that can solve a task in theory may still fail to learn it in practice.

A well-known fix is to start the **forget gate** biased towards "keep the memory". We simply set the forget-gate bias to 1, so the gates begin more open:

```python
print("LSTM with the forget-gate bias set to 1:")
train(remember_bias=True)
```

```output
LSTM with the forget-gate bias set to 1:
  step  50: loss 0.293   test accuracy 0.88
  step 100: loss 0.162   test accuracy 0.97
  step 200: loss 0.157   test accuracy 0.99
  step 300: loss 0.062   test accuracy 0.98
```

With that one small change, the network learns the task within about 100 steps and reaches around 99% accuracy. Nothing tells it that the first step is special: it **discovers** that it must carry the sign of the first number through all 15 steps.

Other things that help when a recurrent model will not learn: shorter sequences, a larger hidden size, gradient clipping (already used here), a different learning rate, and, more recently, simply switching to a transformer.

## Shapes and options

| Item | Shape or meaning |
| --- | --- |
| input | `(batch, time, features)` with `batch_first=True` |
| `output` | `(batch, time, hidden)`: the hidden state at **every** step |
| `h_last` | `(layers, batch, hidden)`: the **final** state |
| `num_layers=2` | stack LSTMs for more power |
| `bidirectional=True` | also read the sequence backwards (for tasks where the whole sequence is known) |
| `dropout` | between stacked layers |

## What sequence models do

| Task | Pattern | Example |
| --- | --- | --- |
| **many-to-one** | read the whole sequence, give one answer | sentiment of a review, activity from sensor data |
| **many-to-many** | one output per step | tagging each word |
| **sequence-to-sequence** | read one sequence, write another | translation, summaries |
| **forecasting** | predict the next values | demand, energy use |

## RNNs today

LSTMs and GRUs were the standard for language and speech for years. Since 2017, **transformers** (a later lesson) have replaced them for most language tasks, because they read all positions at once, train much faster on GPUs and handle long-range links better. RNNs are still useful for small problems, streaming data and low-power devices, and understanding them makes transformers easier to understand.

:::interview
**Interviewers often ask:** "Why do LSTMs work better than vanilla RNNs?" Plain RNNs suffer from vanishing gradients through time, so they forget long-range information. LSTMs add a cell state with forget, input and output gates, giving a path along which information and gradients can flow across many steps with little change.
:::
