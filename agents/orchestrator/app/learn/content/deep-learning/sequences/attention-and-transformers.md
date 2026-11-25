---
title: Attention and transformers
summary: Understand self-attention step by step, build it in NumPy and check it against PyTorch, then see how transformers are assembled and why they took over.
takeaways:
- Attention lets every position look at every other position and decide what matters
- Self-attention uses queries, keys and values: weights come from softmax(Q·Kᵀ / √d)
- A transformer stacks attention and feed-forward layers with residual connections and layer normalisation
---
## The idea: look at what matters

Read this sentence: "The animal did not cross the road because **it** was too tired." What does "it" refer to? You looked back at "the animal", not "the road". **Attention** gives a network this ability: when processing one word, it can **look at all the other words** and decide how much each one matters.

RNNs pass information along one step at a time, and distant words become faint. With attention, every position can connect **directly** to every other position.

## Queries, keys and values

Each token produces three vectors:

| Vector | Think of it as | Role |
| --- | --- | --- |
| **Query (Q)** | "what am I looking for?" | the token that is asking |
| **Key (K)** | "what do I contain?" | what each token offers, to be matched against queries |
| **Value (V)** | "the information I will hand over" | what actually gets passed on |

The steps for one token:

1. Compare its **query** with every token's **key** (a dot product): a high score means a good match.
2. Turn the scores into weights that add up to 1 with **softmax**.
3. Take the weighted average of the **values**.

`Attention(Q, K, V) = softmax( Q · Kᵀ / √d ) · V`. The division by `√d` (the vector size) keeps the scores from growing too large.

## Attention in NumPy

Three tokens, each described by a 4-number vector:

```python
import numpy as np

rng = np.random.default_rng(0)
tokens, d = 3, 4
Q = rng.normal(size=(tokens, d))
K = rng.normal(size=(tokens, d))
V = rng.normal(size=(tokens, d))

def softmax(scores):
    e = np.exp(scores - scores.max(axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)

scores = Q @ K.T / np.sqrt(d)               # how well each query matches each key: a 3 x 3 table
weights = softmax(scores)                    # each row becomes probabilities that sum to 1
output = weights @ V                         # a weighted mix of the values

print("attention weights (row = who is looking, column = who is looked at):")
print(np.round(weights, 2))
print("each row adds up to:", np.round(weights.sum(axis=1), 2))
print("output shape:", output.shape)
```

```output
attention weights (row = who is looking, column = who is looked at):
[[0.23 0.48 0.3 ]
 [0.14 0.6  0.26]
 [0.67 0.24 0.1 ]]
each row adds up to: [1. 1. 1.]
output shape: (3, 4)
```

Each row shows how one token distributes its attention over all three tokens. The output for each token is a blend of the values, weighted by that attention.

## Checking against PyTorch

```python
import torch
import torch.nn.functional as F

reference = F.scaled_dot_product_attention(torch.tensor(Q)[None], torch.tensor(K)[None], torch.tensor(V)[None])
print("our NumPy attention matches PyTorch:", np.allclose(output, reference[0].numpy()))
```

```output
our NumPy attention matches PyTorch: True
```

That is genuinely all that attention is. The scaled dot-product attention inside the largest language models is this same calculation, run on bigger arrays.

## Self-attention and masks

In **self-attention**, Q, K and V all come from the **same** sequence, so each token gathers information from the others in its own sentence. For text generation (predicting the next word), a token must **not** see the future, so we hide those positions with a **causal mask**:

```python
mask = np.tril(np.ones((tokens, tokens)))                 # 1 where looking is allowed (lower triangle)
masked_scores = np.where(mask == 1, scores, -1e9)
causal_weights = softmax(masked_scores)
print(np.round(causal_weights, 2))
```

```output
[[1.   0.   0.  ]
 [0.19 0.81 0.  ]
 [0.67 0.24 0.1 ]]
```

The upper-right numbers are 0: the first token can only look at itself, the second at itself and the first, and so on. GPT-style models use this causal mask; BERT-style models, which read whole sentences, do not.

## Multi-head attention

One attention pattern is limiting. **Multi-head attention** runs several attentions in parallel, each with its own Q, K, V projections, and joins the results. One head might track grammar, another which noun a pronoun refers to.

```python
import torch
from torch import nn

torch.manual_seed(0)
attention = nn.MultiheadAttention(embed_dim=8, num_heads=2, batch_first=True)

x = torch.randn(2, 5, 8)                                   # 2 sentences, 5 tokens, 8 numbers per token
out, attn_weights = attention(x, x, x)                     # self-attention: query = key = value = x
print("output shape           :", tuple(out.shape))
print("attention weights shape:", tuple(attn_weights.shape), "(batch, who looks, who is looked at)")
print("parameters:", sum(p.numel() for p in attention.parameters()))
```

```output
output shape           : (2, 5, 8)
attention weights shape: (2, 5, 5) (batch, who looks, who is looked at)
parameters: 288
```

The output has the same shape as the input, so layers can be stacked. The weights tensor is a 5 by 5 table for each sentence.

## Position: attention has no sense of order

Attention treats its input as a set: shuffle the words and, without extra help, it gives the same answer for each word. To give it a sense of order, we **add a position signal** to every embedding. The original transformer used sine and cosine waves of different frequencies:

```python
def positional_encoding(positions, dimension):
    pe = np.zeros((positions, dimension))
    for pos in range(positions):
        for i in range(0, dimension, 2):
            angle = pos / (10000 ** (i / dimension))
            pe[pos, i] = np.sin(angle)
            pe[pos, i + 1] = np.cos(angle)
    return pe

pe = positional_encoding(4, 8)
print("shape:", pe.shape)
print("position 0:", np.round(pe[0], 2))
print("position 1:", np.round(pe[1], 2))
```

```output
shape: (4, 8)
position 0: [0. 1. 0. 1. 0. 1. 0. 1.]
position 1: [0.84 0.54 0.1  1.   0.01 1.   0.   1.  ]
```

Each position gets its own unique pattern. Many modern models learn positions instead, or use rotary embeddings (RoPE), but the purpose is identical.

## The transformer block

A transformer is a stack of identical blocks. Each block has:

1. **Multi-head self-attention**: tokens exchange information.
2. **Feed-forward network**: a small dense network applied to each token separately (where much of the knowledge is stored).
3. A **residual connection** (add the input back) and **layer normalisation** around each part.

```python
layer = nn.TransformerEncoderLayer(d_model=8, nhead=2, dim_feedforward=16, batch_first=True)
stack = nn.TransformerEncoder(layer, num_layers=3)

x = torch.randn(2, 5, 8)
print("output shape:", tuple(stack(x).shape))
print("parameters in one block:", sum(p.numel() for p in layer.parameters()))
print("parameters in 3 blocks :", sum(p.numel() for p in stack.parameters()))
```

```output
output shape: (2, 5, 8)
parameters in one block: 600
parameters in 3 blocks : 1800
```

The shape never changes, which is why you can stack 12, 24 or 96 blocks. Scaling up means a bigger `d_model`, more heads, more blocks, and more training data.

## Why transformers won

| Advantage | Reason |
| --- | --- |
| **parallel training** | all positions are processed at once, unlike an RNN's step-by-step loop; perfect for GPUs |
| **long-range connections** | any token links directly to any other |
| **scaling** | performance keeps improving as data, size and compute grow |
| **flexibility** | the same design works for text, images (ViT), audio, proteins |

The cost: attention compares every token with every other, so memory and compute grow with the **square** of the sequence length:

```python
for length in (512, 2048, 8192, 32768):
    print(f"{length:>6} tokens -> {length * length:>13,} attention scores per head per layer")
```

```output
   512 tokens ->       262,144 attention scores per head per layer
  2048 tokens ->     4,194,304 attention scores per head per layer
  8192 tokens ->    67,108,864 attention scores per head per layer
 32768 tokens -> 1,073,741,824 attention scores per head per layer
```

Doubling the length makes the attention table four times bigger. This is why long context windows are expensive, and why research on efficient attention (FlashAttention, sparse and linear attention) is so active.

## Three families

| Type | Example | Reads | Good for |
| --- | --- | --- | --- |
| **encoder-only** | BERT | the whole text both ways | classification, search, understanding |
| **decoder-only** | GPT, Llama | left to right (causal mask) | generating text, chat assistants |
| **encoder-decoder** | T5, original transformer | an input, then writes an output | translation, summarising |

:::interview
**Interviewers often ask:** "Explain self-attention." Each token is projected into a query, a key and a value. Attention weights come from softmax(QKᵀ/√d): how well each query matches every key. The output for each token is the weighted sum of the values, so every token can gather information from all the others in one step. "Why divide by √d?" Dot products grow with the dimension, which would push the softmax into saturation and kill gradients; scaling keeps the values in a good range.
:::
