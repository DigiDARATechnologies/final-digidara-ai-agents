---
title: Building models with nn.Module
summary: Define networks with torch.nn, inspect their parameters, write your own Module, and understand training and evaluation modes.
takeaways:
- nn.Sequential stacks layers; subclassing nn.Module gives full control over the forward pass
- model.parameters() lists every learnable weight; counting them tells you the model's size
- model.train() and model.eval() switch layers like Dropout and BatchNorm between modes
---
## nn.Sequential: layers in a row

The quickest way to build a network:

```python
import torch
from torch import nn

torch.manual_seed(0)

model = nn.Sequential(
    nn.Linear(4, 8),      # 4 inputs -> 8 neurons
    nn.ReLU(),
    nn.Linear(8, 3),      # 8 -> 3 outputs (for 3 classes)
)
print(model)

x = torch.randn(5, 4)     # a batch of 5 examples with 4 features
out = model(x)
print("input :", tuple(x.shape))
print("output:", tuple(out.shape))
```

```output
Sequential(
  (0): Linear(in_features=4, out_features=8, bias=True)
  (1): ReLU()
  (2): Linear(in_features=8, out_features=3, bias=True)
)
input : (5, 4)
output: (5, 3)
```

`nn.Linear(4, 8)` is the dense layer we wrote by hand: a weight matrix and a bias. Calling `model(x)` runs the forward pass.

## Parameters

```python
for name, parameter in model.named_parameters():
    print(f"{name:<12} shape {tuple(parameter.shape)}")

total = sum(p.numel() for p in model.parameters())
print("total parameters:", total)
```

```output
0.weight     shape (8, 4)
0.bias       shape (8,)
2.weight     shape (3, 8)
2.bias       shape (3,)
total parameters: 67
```

The count is `4×8 + 8` for the first layer plus `8×3 + 3` for the second: 40 + 27 = 67 parameters. Always check parameter counts: they show how big the model is and whether the shapes are what you intended.

## Your own Module

For anything beyond a straight line of layers, write a class:

```python
class Classifier(nn.Module):
    def __init__(self, n_features, n_hidden, n_classes):
        super().__init__()                              # always call this first
        self.layer1 = nn.Linear(n_features, n_hidden)
        self.layer2 = nn.Linear(n_hidden, n_hidden)
        self.output = nn.Linear(n_hidden, n_classes)
        self.activation = nn.ReLU()
        self.dropout = nn.Dropout(0.5)

    def forward(self, x):
        h = self.activation(self.layer1(x))
        h = self.dropout(h)
        h = self.activation(self.layer2(h)) + h         # a "skip connection": add the input back
        return self.output(h)

net = Classifier(n_features=4, n_hidden=16, n_classes=3)
print(sum(p.numel() for p in net.parameters()), "parameters")
print(tuple(net(torch.randn(7, 4)).shape))
```

```output
403 parameters
(7, 3)
```

The pattern never changes:

1. `__init__`: **create** the layers (they register their parameters automatically).
2. `forward`: **describe** how data flows through them.

You never write `backward`: autograd derives it from `forward`. The `+ h` line is a **skip (residual) connection**, an idea that made very deep networks trainable.

## train() and eval() modes

Some layers behave differently while training and while predicting. **Dropout** randomly switches off units during training, but must do nothing at prediction time:

```python
net = Classifier(4, 16, 3)
x = torch.randn(1, 4)

net.train()
a = net(x)
b = net(x)
print("train mode, same input twice gives the same output:", torch.allclose(a, b))

net.eval()
with torch.no_grad():
    a = net(x)
    b = net(x)
print("eval mode,  same input twice gives the same output:", torch.allclose(a, b))
```

```output
train mode, same input twice gives the same output: False
eval mode,  same input twice gives the same output: True
```

In training mode, dropout makes each pass different (on purpose). In evaluation mode, the output is repeatable.

:::warning
Forgetting `model.eval()` before testing is a very common bug: dropout stays active, batch normalisation uses the wrong statistics, and your test results are noisy and worse than they should be. Always: `model.eval()` and `torch.no_grad()` when testing, `model.train()` when training.
:::

## Common layers

| Layer | Use |
| --- | --- |
| `nn.Linear(in, out)` | dense layer |
| `nn.ReLU()`, `nn.GELU()`, `nn.Sigmoid()`, `nn.Softmax(dim=1)` | activations |
| `nn.Dropout(p)` | randomly zero a share `p` of the values (regularisation) |
| `nn.BatchNorm1d(n)`, `nn.LayerNorm(n)` | normalise activations |
| `nn.Conv2d(in_ch, out_ch, k)` | convolution for images |
| `nn.LSTM`, `nn.GRU` | recurrent layers for sequences |
| `nn.Embedding(vocab, dim)` | lookup table for words and categories |
| `nn.MultiheadAttention`, `nn.TransformerEncoderLayer` | attention and transformers |

## Choosing the output layer

Remember: leave out sigmoid and softmax in the model's last layer if you use `BCEWithLogitsLoss` or `CrossEntropyLoss`. They apply it for you. Apply sigmoid or softmax **only when you need probabilities** at prediction time:

```python
logits = torch.tensor([[2.0, 1.0, 0.1]])
print("probabilities:", [round(v, 3) for v in torch.softmax(logits, dim=1)[0].tolist()])
print("predicted class:", logits.argmax(dim=1).item())
```

```output
probabilities: [0.659, 0.242, 0.099]
predicted class: 0
```

Notice that the predicted class (the `argmax`) is the same whether you look at logits or probabilities, so for plain classification you often do not need the softmax at all.

## Saving the idea in one line

A model is just a **function with learnable numbers inside it**. `nn.Module` is the container that keeps track of those numbers, so the optimiser can find and update all of them.
