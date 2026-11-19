---
title: Initialisation, normalisation and vanishing gradients
summary: See why deep networks are hard to train, measure vanishing gradients, and fix them with ReLU, good initialisation and batch normalisation.
takeaways:
- In deep networks, signals and gradients can shrink to nothing or blow up as they pass through layers
- ReLU, careful initialisation (Xavier, Kaiming) and normalisation layers keep them healthy
- Skip connections let gradients flow straight through very deep models
---
## Why depth is hard

Backpropagation multiplies many numbers together, one for each layer. Multiply many numbers smaller than 1 and the result becomes **tiny** (a **vanishing gradient**); multiply many larger than 1 and it becomes **huge** (an **exploding gradient**). The early layers either stop learning or become unstable.

## Measuring a vanishing gradient

We build a 10-layer network twice, with sigmoid and with ReLU, and measure the size of the gradient reaching the **first** layer compared with the **last**:

```python
import torch
from torch import nn

def deep_net(activation, depth=10, width=32):
    layers = []
    for _ in range(depth):
        layers += [nn.Linear(width, width), activation()]
    layers.append(nn.Linear(width, 1))
    return nn.Sequential(*layers)

def gradient_sizes(activation):
    torch.manual_seed(0)
    net = deep_net(activation)
    x, y = torch.randn(64, 32), torch.randn(64, 1)
    loss = nn.functional.mse_loss(net(x), y)
    loss.backward()
    linears = [m for m in net if isinstance(m, nn.Linear)]
    return linears[0].weight.grad.norm().item(), linears[-1].weight.grad.norm().item()

for name, activation in (("sigmoid", nn.Sigmoid), ("ReLU", nn.ReLU)):
    first, last = gradient_sizes(activation)
    print(f"{name:<8} gradient at first layer {first:.2e}   last layer {last:.2e}   ratio {first / last:.1e}")
```

```output
sigmoid  gradient at first layer 7.01e-09   last layer 1.05e+00   ratio 6.7e-09
ReLU     gradient at first layer 1.44e-04   last layer 1.14e-01   ratio 1.3e-03
```

With sigmoid, the gradient reaching the first layer is about **a billion times smaller** than at the last layer (7e-9 against 1.05): the early layers get no learning signal at all. With ReLU the gradient still shrinks (about a thousandfold here, because the default initialisation is not tuned for depth 10) but it is hundreds of thousands of times larger than with sigmoid, which is enough to learn. This is why networks were hard to train deeply until ReLU and better initialisation arrived. (The sigmoid's slope is at most 0.25, so each layer shrinks the gradient by at least a factor of 4.)

## Initialisation matters

Weights must start at a sensible scale. If they start too small, the signal fades layer by layer; too big, it explodes. Watch the size (standard deviation) of the activations in a 20-layer network under different starting scales:

```python
def activation_spread(init_std, depth=20, width=256, activation=torch.tanh):
    torch.manual_seed(0)
    x = torch.randn(512, width)
    sizes = []
    for layer in range(depth):
        weight = torch.randn(width, width) * init_std
        x = activation(x @ weight)
        sizes.append(x.std().item())
    return sizes[0], sizes[4], sizes[9], sizes[19]

print("std of activations after layer:        1      5      10      20")
for label, std in (("too small (0.01)", 0.01), ("too big (1.0)", 1.0), ("Xavier (1/sqrt(width))", 256 ** -0.5)):
    a, b, c, d = activation_spread(std)
    print(f"{label:<24}  {a:>8.4f} {b:>8.4f} {c:>8.4f} {d:>8.4f}")
```

```output
std of activations after layer:        1      5      10      20
too small (0.01)            0.1561   0.0001   0.0000   0.0000
too big (1.0)               0.9745   0.9740   0.9743   0.9745
Xavier (1/sqrt(width))      0.6276   0.3236   0.2321   0.1542
```

- **Too small**: the signal shrinks towards zero (the network outputs almost nothing, and gradients vanish).
- **Too big**: the tanh units saturate near ±1 (the spread stays at about 0.97 in every layer), where their gradient is almost zero.
- **Xavier scaling** (the weight size is 1 over the square root of the layer width) keeps the signal alive: it shrinks gently (from 0.63 to 0.15 over 20 layers) instead of vanishing to nothing or getting stuck at the saturated value of about 0.97.

| Initialisation | For | Rule |
| --- | --- | --- |
| **Xavier / Glorot** | tanh, sigmoid | variance about `1 / fan_in` (or `2 / (fan_in + fan_out)`) |
| **Kaiming / He** | ReLU | variance `2 / fan_in` (ReLU zeroes half the signal, so it needs more) |

PyTorch's `nn.Linear` already uses a sensible default, but for custom layers use `nn.init.kaiming_normal_` or `nn.init.xavier_uniform_`.

## Batch normalisation

**Batch normalisation** re-centres and rescales the activations inside the network, batch by batch, so each layer receives inputs with a stable mean and spread:

```python
torch.manual_seed(0)
batch = torch.randn(256, 4) * 10 + 50           # features with mean about 50 and std about 10
norm = nn.BatchNorm1d(4)

norm.train()
out = norm(batch)
print("before: mean", round(batch.mean().item(), 1), " std", round(batch.std().item(), 1))
print("after : mean", round(out.mean().item(), 3), " std", round(out.std().item(), 3))
```

```output
before: mean 50.3  std 10.3
after : mean -0.0  std 1.0
```

After normalising, each feature has mean about 0 and standard deviation about 1. The layer then applies a learnable scale and shift, so it can undo the normalisation if that helps.

Why it helps: training is faster and more stable, you can use larger learning rates, and it gives a mild regularising effect. During evaluation, it uses running averages gathered during training instead of the current batch (another reason `model.eval()` matters).

| Normalisation | Normalises over | Typical use |
| --- | --- | --- |
| **BatchNorm** | the batch, per feature | convolutional networks |
| **LayerNorm** | the features of one example | **transformers**, RNNs, small batches |
| **GroupNorm** | groups of channels | small-batch vision |
| **RMSNorm** | like LayerNorm, simpler | many modern language models |

## Skip (residual) connections

A **residual connection** adds a layer's input to its output: `output = x + layer(x)`. The gradient then has a direct, unobstructed path back through the `+`, no matter how deep the stack. This simple idea (ResNet, 2015) made networks with hundreds of layers trainable, and every transformer uses it.

```python
class ResidualBlock(nn.Module):
    def __init__(self, width):
        super().__init__()
        self.layer = nn.Sequential(nn.Linear(width, width), nn.ReLU(), nn.Linear(width, width))

    def forward(self, x):
        return x + self.layer(x)                 # the skip connection

torch.manual_seed(0)
plain = nn.Sequential(*[nn.Sequential(nn.Linear(32, 32), nn.Sigmoid()) for _ in range(30)], nn.Linear(32, 1))
residual = nn.Sequential(*[ResidualBlock(32) for _ in range(30)], nn.Linear(32, 1))

def first_layer_gradient(net):
    x, y = torch.randn(64, 32), torch.randn(64, 1)
    nn.functional.mse_loss(net(x), y).backward()
    first = next(p for p in net.parameters() if p.dim() == 2)
    return first.grad.norm().item()

print(f"30-layer plain sigmoid network  : gradient at the first layer {first_layer_gradient(plain):.2e}")
print(f"30-layer residual network       : gradient at the first layer {first_layer_gradient(residual):.2e}")
```

```output
30-layer plain sigmoid network  : gradient at the first layer 0.00e+00
30-layer residual network       : gradient at the first layer 1.01e+00
```

In the plain 30-layer sigmoid network the first layer receives essentially **zero** gradient. In the residual network it receives a healthy gradient, even though the network is just as deep.

## The toolbox for healthy deep networks

| Problem | Fix |
| --- | --- |
| vanishing gradients | ReLU or GELU, good initialisation, normalisation, residual connections |
| exploding gradients | gradient clipping, lower learning rate, normalisation |
| dead ReLUs | Leaky ReLU, lower learning rate, better initialisation |
| slow, unstable training | normalisation layers, Adam, a learning rate warm-up |

:::interview
**Interviewers often ask:** "What is the vanishing gradient problem and how do you solve it?" During backpropagation the gradient is a product of many per-layer factors; if they are below 1 (as with sigmoid or tanh) the gradient shrinks exponentially toward the early layers, so they learn very slowly. Use ReLU-type activations, proper initialisation (Xavier or Kaiming), batch or layer normalisation, residual connections, and for RNNs gated cells such as LSTM.
:::
