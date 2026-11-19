---
title: Autoencoders and generative models
summary: Compress and rebuild data with an autoencoder, use reconstruction error to spot anomalies, and get an overview of VAEs, GANs and diffusion models.
takeaways:
- An autoencoder learns to squeeze data into a small code and rebuild it, with no labels needed
- Reconstruction error flags inputs unlike the training data, which is useful for anomaly detection
- Generative models (VAEs, GANs, diffusion, language models) learn to create new data
---
## Learning without labels

Everything so far used labelled data. An **autoencoder** learns from the data **alone**. It has two halves:

- an **encoder** squeezes the input into a small **code** (the bottleneck),
- a **decoder** tries to rebuild the original input from that code.

The training target is the **input itself**. Because the code is much smaller than the input, the network is forced to keep only the most important information.

```py
input (64 numbers) -> encoder -> code (8 numbers) -> decoder -> output (64 numbers, should match the input)
```

## Build one for handwritten digits

```python
import numpy as np
import torch
from torch import nn
from sklearn.datasets import load_digits
from sklearn.decomposition import PCA
from sklearn.model_selection import train_test_split

torch.manual_seed(0)
X = load_digits().data / 16.0                               # 64 pixel values per image, scaled to 0..1
X_train, X_test = train_test_split(X, test_size=0.25, random_state=0)
Xt = torch.tensor(X_train, dtype=torch.float32)
Xv = torch.tensor(X_test, dtype=torch.float32)

autoencoder = nn.Sequential(
    nn.Linear(64, 32), nn.ReLU(),
    nn.Linear(32, 8),                       # the bottleneck: just 8 numbers describe each image
    nn.Linear(8, 32), nn.ReLU(),
    nn.Linear(32, 64), nn.Sigmoid(),        # outputs between 0 and 1, like the pixels
)
optimizer = torch.optim.Adam(autoencoder.parameters(), lr=0.005)

for epoch in range(1, 201):
    loss = nn.functional.mse_loss(autoencoder(Xt), Xt)          # the target is the input itself
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    if epoch in (1, 20, 100, 200):
        with torch.no_grad():
            test_loss = nn.functional.mse_loss(autoencoder(Xv), Xv).item()
        print(f"epoch {epoch:>3}: train error {loss.item():.4f}   test error {test_loss:.4f}")
```

```output
epoch   1: train error 0.1837   test error 0.1805
epoch  20: train error 0.0853   test error 0.0842
epoch 100: train error 0.0336   test error 0.0353
epoch 200: train error 0.0207   test error 0.0233
```

The reconstruction error falls as the network learns to describe each 64-pixel picture with 8 numbers.

## Compared with PCA

PCA (from the machine learning course) is the classic linear way to compress data. With the same 8-number code, how do they compare?

```python
pca = PCA(n_components=8).fit(X_train)
pca_error = float(np.mean((pca.inverse_transform(pca.transform(X_test)) - X_test) ** 2))

with torch.no_grad():
    ae_error = nn.functional.mse_loss(autoencoder(Xv), Xv).item()

print(f"PCA with 8 components, test error  : {pca_error:.4f}")
print(f"autoencoder with 8 numbers, test error: {ae_error:.4f}")
```

```output
PCA with 8 components, test error  : 0.0249
autoencoder with 8 numbers, test error: 0.0233
```

An autoencoder with only linear layers would be equivalent to PCA. With non-linear activations it can capture curved structure, so it can match or beat PCA at the same code size, especially on complex data like photos. On this small, simple dataset the two are close.

## Anomaly detection with reconstruction error

A network trained only on normal data rebuilds normal data well, but rebuilds **unfamiliar** data badly. That gap detects anomalies (faulty parts, fraud, intrusions):

```python
with torch.no_grad():
    normal_error = ((autoencoder(Xv) - Xv) ** 2).mean(dim=1)
    noise = torch.rand(len(Xv), 64)                                  # random static: nothing like a digit
    noise_error = ((autoencoder(noise) - noise) ** 2).mean(dim=1)

threshold = normal_error.quantile(0.95).item()
print("typical reconstruction error, real digits :", round(normal_error.mean().item(), 4))
print("typical reconstruction error, random noise:", round(noise_error.mean().item(), 4))
print("noise images above the threshold:", f"{(noise_error > threshold).float().mean().item():.0%}")
print("real digits above the threshold :", f"{(normal_error > threshold).float().mean().item():.0%}")
```

```output
typical reconstruction error, real digits : 0.0233
typical reconstruction error, random noise: 0.1702
noise images above the threshold: 100%
real digits above the threshold : 5%
```

Random static is rebuilt far worse than real digits, so a threshold set on normal data flags almost all of it while flagging only about 5% of normal digits by design. This one-class idea is widely used when you have plenty of "normal" examples and almost no examples of failure.

## Other uses of autoencoders

| Use | How |
| --- | --- |
| **compression** and dimensionality reduction | use the code as features |
| **denoising** | train to rebuild the clean image from a noisy copy |
| **anomaly detection** | large reconstruction error means unusual |
| **pretraining** | learn features from unlabelled data, then fine-tune |

## Generative models: creating new data

An autoencoder can compress and rebuild but cannot invent, because its code space has gaps. **Generative models** learn the distribution of the data well enough to sample **new** examples.

| Model | Idea | Known for |
| --- | --- | --- |
| **VAE** (variational autoencoder) | the encoder outputs a probability distribution, and the code space is smooth, so you can sample new codes | smooth latent spaces, simple to train |
| **GAN** (generative adversarial network) | a **generator** makes fakes and a **discriminator** tries to spot them, each improving the other | sharp images (older face generators) |
| **Diffusion models** | learn to **remove noise** step by step; generate by starting from pure noise and denoising | Stable Diffusion, DALL-E, state-of-the-art images and video |
| **Autoregressive language models** | predict the next token, over and over | GPT, Llama, Claude: text and code |

Diffusion and large language models dominate generative AI today. All of them are built from the pieces you now know: layers, losses, backpropagation, and attention.

:::warning
Generative models can produce convincing but false or harmful content. Anything built on them needs checks for accuracy, bias, copyright and misuse (see the responsible AI section in the last lesson).
:::

:::interview
**Interviewers often ask:** "What is an autoencoder and what is it used for?" A network trained to reconstruct its own input through a narrow bottleneck, so it learns a compact representation. It is used for compression, denoising, pretraining and anomaly detection (high reconstruction error signals unusual data). "What is the difference between a GAN and a VAE?" A VAE learns a probabilistic latent space by maximising a likelihood bound, giving smooth sampling; a GAN trains a generator against a discriminator, often giving sharper samples but with less stable training.
:::
