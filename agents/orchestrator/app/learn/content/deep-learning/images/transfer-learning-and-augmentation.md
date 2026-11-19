---
title: Transfer learning
summary: Reuse a network trained on one task for another, see the benefit with a small experiment, and learn the freeze-and-fine-tune recipe used in real projects.
takeaways:
- Early layers learn general features that transfer well to new tasks
- Freeze the pretrained layers, replace the final layer and train it on your small dataset
- With little data, transfer learning is usually far better than training from scratch
---
## The idea

Training a good image model from nothing needs millions of images and days of computing. But a network trained on a huge dataset has already learned useful **general** features: edges, textures, shapes. Those features help with almost any image task. So instead of starting from random weights, we start from a **pretrained** network and adapt it. This is **transfer learning**, and it is how most practical computer vision (and language) work is done.

| Approach | Data needed | Time | Result with small data |
| --- | --- | --- | --- |
| train from scratch | a lot | long | often poor |
| **feature extraction**: freeze everything, train a new final layer | little | very short | often good |
| **fine-tuning**: unfreeze some or all layers and train gently | moderate | short | usually the best |

## A small experiment you can run

We simulate the situation with the digits data. **Pretraining task**: recognise all ten digits using 1,000 labelled images. **New task**: decide whether a digit is **even or odd**, but with only a handful of labelled examples. Does reusing the digit-recognising layers help?

```python
import copy
import numpy as np
import torch
from torch import nn
from sklearn.datasets import load_digits

digits = load_digits()
images = torch.tensor(digits.images / 16.0, dtype=torch.float32).unsqueeze(1)
labels = torch.tensor(digits.target, dtype=torch.long)

def features():
    return nn.Sequential(
        nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Flatten(),
    )

def fit(model, X, y, epochs, lr=0.01):
    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.Adam(params, lr=lr)
    for _ in range(epochs):
        model.train()
        loss = nn.functional.cross_entropy(model(X), y)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

def accuracy(model, X, y):
    model.eval()
    with torch.no_grad():
        return (model(X).argmax(dim=1) == y).float().mean().item()

order = torch.randperm(len(images), generator=torch.Generator().manual_seed(0))
pretrain_idx, new_idx = order[:1000], order[1000:]
X_pre, y_pre = images[pretrain_idx], labels[pretrain_idx]
X_new, y_new = images[new_idx], labels[new_idx] % 2            # the new task: even (0) or odd (1)

print("labelled examples | from scratch | frozen pretrained features | fine-tuned")
for n_labelled in (6, 20, 40):
    scratch_scores, frozen_scores, tuned_scores = [], [], []
    for seed in range(8):
        torch.manual_seed(seed)
        shuffled = torch.randperm(len(X_new))
        train_idx, test_idx = shuffled[:n_labelled], shuffled[n_labelled:]
        X_tr, y_tr, X_te, y_te = X_new[train_idx], y_new[train_idx], X_new[test_idx], y_new[test_idx]

        pretrained = features()                                            # learn general features on the big task
        fit(nn.Sequential(pretrained, nn.Linear(128, 10)), X_pre, y_pre, epochs=60)

        scratch = nn.Sequential(features(), nn.Linear(128, 2))              # option 1: no pretraining
        fit(scratch, X_tr, y_tr, epochs=60)
        scratch_scores.append(accuracy(scratch, X_te, y_te))

        frozen_backbone = copy.deepcopy(pretrained)                         # option 2: freeze the features, train a new head
        for p in frozen_backbone.parameters():
            p.requires_grad = False
        frozen = nn.Sequential(frozen_backbone, nn.Linear(128, 2))
        fit(frozen, X_tr, y_tr, epochs=60)
        frozen_scores.append(accuracy(frozen, X_te, y_te))

        tuned = nn.Sequential(copy.deepcopy(pretrained), nn.Linear(128, 2)) # option 3: fine-tune everything, gently
        fit(tuned, X_tr, y_tr, epochs=60, lr=0.002)
        tuned_scores.append(accuracy(tuned, X_te, y_te))

    print(f"{n_labelled:>17} | {np.mean(scratch_scores):>12.3f} | {np.mean(frozen_scores):>26.3f} | {np.mean(tuned_scores):>10.3f}")
```

```output
labelled examples | from scratch | frozen pretrained features | fine-tuned
                6 |        0.679 |                      0.717 |      0.716
               20 |        0.787 |                      0.801 |      0.789
               40 |        0.849 |                      0.856 |      0.842
```

Each row is the average of 8 random splits (one run on a few examples is far too noisy to trust). Read the pattern, not just the numbers:

- With **very few labelled examples** (6), the pretrained features give the biggest edge over training from scratch.
- The advantage **shrinks as labelled data grows**, and with 40 examples it has almost vanished. Plenty of data lets a network learn the features itself.
- The gain here is **modest** because this is a tiny network and tiny 8 by 8 images. With a real ResNet pretrained on millions of photos, transfer is often the difference between a useless model and an excellent one.

:::warning
Transfer is not magic: it works when the original task is **broad and related**. We also tried reusing features learned only on digits 0 to 4 for recognising digits 5 to 9 (a narrower, different job). With 40 examples that did **not** help: training from scratch scored 0.91 against 0.88 for the frozen features. Always compare against a from-scratch baseline instead of assuming pretraining helps.
:::

## The freeze-and-replace recipe

With a real pretrained model from `torchvision`:

```py
import torch
from torch import nn
from torchvision import models

weights = models.ResNet18_Weights.DEFAULT
model = models.resnet18(weights=weights)           # downloads the pretrained network (trained on ImageNet)
preprocess = weights.transforms()                  # the exact resizing and normalising it expects

for parameter in model.parameters():
    parameter.requires_grad = False                # 1. freeze every pretrained layer

model.fc = nn.Linear(model.fc.in_features, 5)      # 2. replace the final layer: 5 classes of OUR problem

optimizer = torch.optim.Adam(model.fc.parameters(), lr=1e-3)    # 3. train only the new layer
```

After the new layer has learned, you can optionally **fine-tune**: unfreeze some or all layers and continue training with a **much smaller learning rate** (`1e-5` to `1e-4`), so the pretrained knowledge is nudged, not destroyed.

## Counting what you train

```python
backbone = features()
model = nn.Sequential(backbone, nn.Linear(128, 5))
total = sum(p.numel() for p in model.parameters())

for p in backbone.parameters():
    p.requires_grad = False
trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f"total parameters    : {total}")
print(f"trainable parameters: {trainable} ({100 * trainable / total:.1f}%)")
```

```output
total parameters    : 5445
trainable parameters: 645 (11.8%)
```

Freezing leaves only the new final layer to train. With a real ResNet-18 and a 5-class head, that means training just 2,565 parameters out of about 11.2 million, which is fast and needs little data.

## Practical tips

| Tip | Why |
| --- | --- |
| use the **same preprocessing** the pretrained model was trained with | the weights expect inputs on that scale |
| start with a **frozen** backbone, then fine-tune gently | protects the pretrained knowledge |
| use a **small learning rate** when fine-tuning | big updates wipe out what was learned |
| use **data augmentation** on the small dataset | reduces overfitting |
| the more similar your data is to the pretraining data, the more it helps | photos help with photos more than with X-rays, but even then it usually helps |
| for text, start from a pretrained **language model** (BERT, GPT-style) | the same idea, now standard in NLP |

Where to find pretrained models: `torchvision.models` (vision), **Hugging Face** (thousands of models for text, vision and audio), and `timm` (many vision models).

:::interview
**Interviewers often ask:** "What is transfer learning and when do you use it?" Reusing a model pretrained on a large dataset as the starting point for a new task, by freezing the early general-feature layers and training a new head (feature extraction), or by fine-tuning all layers at a low learning rate. Use it when you have limited data or compute, which is most of the time.
:::
