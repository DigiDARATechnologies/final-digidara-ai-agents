---
title: Convolutional neural networks (images)
summary: Understand convolution, filters, padding, stride and pooling, verify them by hand, and train a CNN that reads handwritten digits.
takeaways:
- A convolution slides a small filter over the image, detecting a pattern wherever it appears
- Convolution layers share their weights, so they need far fewer parameters than dense layers
- A CNN stacks convolution, activation and pooling, then a dense layer to classify
---
## Why not just use dense layers for images?

A 200 by 200 colour photo has 120,000 numbers. A dense layer with 1,000 neurons would need **120 million weights**, and it would treat the pixel at the top-left as unrelated to its neighbours. Images have structure: nearby pixels belong together, and a cat's ear looks the same wherever it appears in the picture.

A **convolutional neural network (CNN)** uses this structure:

| Idea | Meaning |
| --- | --- |
| **local connections** | each neuron looks only at a small patch, not the whole image |
| **weight sharing** | the same small filter is used at every position |
| **translation invariance** | a pattern is detected wherever it is |
| **hierarchy** | early layers find edges, later layers find shapes, then objects |

## Convolution by hand

A **filter** (or kernel) is a small grid of weights. Place it over a patch of the image, multiply matching numbers, add them up, and that gives one output number. Slide it across the image to build a **feature map**.

Here is a 6 by 6 image that is dark on the left and bright on the right, and a filter that detects **vertical edges**:

```python
import numpy as np
import torch
import torch.nn.functional as F

image = np.zeros((6, 6))
image[:, 3:] = 1.0                                   # left half 0, right half 1

kernel = np.array([[-1, 0, 1],
                   [-1, 0, 1],
                   [-1, 0, 1]], dtype=float)         # responds where dark meets bright

def convolve(image, kernel):
    k = kernel.shape[0]
    size = image.shape[0] - k + 1
    out = np.zeros((size, size))
    for i in range(size):
        for j in range(size):
            out[i, j] = np.sum(image[i:i + k, j:j + k] * kernel)
    return out

feature_map = convolve(image, kernel)
print(feature_map)
```

```output
[[0. 3. 3. 0.]
 [0. 3. 3. 0.]
 [0. 3. 3. 0.]
 [0. 3. 3. 0.]]
```

The feature map is zero over flat regions and large exactly where the dark-to-bright edge is (columns 1 and 2 of the output). That is a filter detecting an edge. A CNN **learns** the filter values by training, instead of us choosing them.

## Checking against PyTorch

```python
torch_result = F.conv2d(torch.tensor(image).reshape(1, 1, 6, 6), torch.tensor(kernel).reshape(1, 1, 3, 3))
print("PyTorch gives the same feature map:", np.allclose(torch_result.numpy()[0, 0], feature_map))
```

```output
PyTorch gives the same feature map: True
```

(Strictly speaking, deep learning libraries compute cross-correlation, which is exactly the slide-multiply-add we wrote; the name "convolution" stuck.)

## Shapes: kernel, padding, stride

The size of the output is: **(n + 2 × padding − kernel) / stride + 1** (rounded down).

| Setting | Meaning |
| --- | --- |
| **kernel size** | the filter's width, usually 3 (or 5, 7) |
| **padding** | zeros added around the border, so the output can stay the same size |
| **stride** | how far the filter moves each step; stride 2 halves the size |
| **channels** | the number of layers: 3 for a colour image, and the number of filters in later layers |

```python
x = torch.zeros(1, 1, 8, 8)                       # one 8 x 8 single-channel image

print("kernel 3, no padding        :", tuple(torch.nn.Conv2d(1, 4, 3)(x).shape))
print("kernel 3, padding 1         :", tuple(torch.nn.Conv2d(1, 4, 3, padding=1)(x).shape))
print("kernel 3, stride 2          :", tuple(torch.nn.Conv2d(1, 4, 3, stride=2)(x).shape))
print("max-pool 2 on the 8 x 8     :", tuple(torch.nn.MaxPool2d(2)(x).shape))
```

```output
kernel 3, no padding        : (1, 4, 6, 6)
kernel 3, padding 1         : (1, 4, 8, 8)
kernel 3, stride 2          : (1, 4, 3, 3)
max-pool 2 on the 8 x 8     : (1, 1, 4, 4)
```

The shape is (batch, channels, height, width). With kernel 3 and no padding, 8 shrinks to 6; padding 1 keeps it at 8; stride 2 gives 3; pooling by 2 halves 8 to 4.

## Pooling

**Max pooling** keeps only the largest value in each small window (usually 2 by 2). It shrinks the picture (less computation), keeps the strongest signals, and makes the network a little tolerant to small shifts.

## Parameters: the saving

```python
conv = torch.nn.Conv2d(1, 8, kernel_size=3)
dense = torch.nn.Linear(64, 8 * 6 * 6)               # a dense layer that outputs the same number of values

count = lambda module: sum(p.numel() for p in module.parameters())
print("conv layer parameters :", count(conv), "(8 filters x 9 weights + 8 biases)")
print("dense layer parameters:", count(dense))
```

```output
conv layer parameters : 80 (8 filters x 9 weights + 8 biases)
dense layer parameters: 18720
```

The convolution layer needs only 80 parameters, because the same 8 small filters are reused at every position. The dense layer producing the same number of outputs needs thousands. On real photos the difference is millions.

## A complete CNN on handwritten digits

The `digits` dataset has 1,797 images of 8 by 8 pixels, digits 0 to 9:

```python
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split

torch.manual_seed(0)
digits = load_digits()
X = torch.tensor(digits.images / 16.0, dtype=torch.float32).unsqueeze(1)        # (1797, 1, 8, 8), scaled to 0..1
y = torch.tensor(digits.target, dtype=torch.long)       # class labels for CrossEntropyLoss must be int64
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=0, stratify=y)
print("image batch shape:", tuple(X_train.shape))

cnn = nn.Sequential(
    nn.Conv2d(1, 16, kernel_size=3, padding=1), nn.ReLU(), nn.MaxPool2d(2),     # 8x8 -> 4x4, 16 filters
    nn.Conv2d(16, 32, kernel_size=3, padding=1), nn.ReLU(), nn.MaxPool2d(2),    # 4x4 -> 2x2, 32 filters
    nn.Flatten(),                                                               # 32 * 2 * 2 = 128 numbers
    nn.Linear(128, 10),                                                         # 10 class scores (logits)
)
print("CNN parameters:", sum(p.numel() for p in cnn.parameters()))

loader = DataLoader(TensorDataset(X_train, y_train), batch_size=32, shuffle=True)
optimizer = torch.optim.Adam(cnn.parameters(), lr=0.005)
loss_fn = nn.CrossEntropyLoss()

def test_accuracy():
    cnn.eval()
    with torch.no_grad():
        return (cnn(X_test).argmax(dim=1) == y_test).float().mean().item()

for epoch in range(1, 16):
    cnn.train()
    for xb, yb in loader:
        loss = loss_fn(cnn(xb), yb)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
    if epoch in (1, 3, 5, 15):
        print(f"epoch {epoch:>2}: test accuracy {test_accuracy():.3f}")
```

```output
image batch shape: (1347, 1, 8, 8)
CNN parameters: 6090
epoch  1: test accuracy 0.838
epoch  3: test accuracy 0.951
epoch  5: test accuracy 0.967
epoch 15: test accuracy 0.987
```

Within a few epochs the CNN reads handwritten digits with high accuracy, using only a few thousand parameters. The shapes in the comments show how the picture shrinks (8 by 8 to 4 by 4 to 2 by 2) while the number of **channels** grows (1 to 16 to 32): the network trades spatial size for richer features.

## What the layers learn

| Layer depth | Typically detects |
| --- | --- |
| first | edges and colour blobs |
| middle | corners, textures, simple shapes |
| deep | parts of objects (eyes, wheels), then whole objects |

## Famous architectures

| Network | Year | Known for |
| --- | --- | --- |
| **LeNet** | 1998 | the first successful CNN, digit reading |
| **AlexNet** | 2012 | started the deep learning boom on ImageNet |
| **VGG** | 2014 | very simple, stacked 3 by 3 convolutions |
| **ResNet** | 2015 | residual connections, hundreds of layers |
| **EfficientNet** | 2019 | balancing depth, width and resolution |
| **Vision Transformer (ViT)** | 2020 | transformers applied to image patches |

For real projects you rarely train these from scratch. You start from a **pretrained** one, which is the next lesson.

:::interview
**Interviewers often ask:** "Why are CNNs better than fully connected networks for images?" They exploit local structure with small shared filters, so they need far fewer parameters, detect a pattern wherever it appears (translation invariance) and build up features in a hierarchy from edges to objects. "What is the output size of a convolution?" `(n + 2p − k) / s + 1`.
:::
