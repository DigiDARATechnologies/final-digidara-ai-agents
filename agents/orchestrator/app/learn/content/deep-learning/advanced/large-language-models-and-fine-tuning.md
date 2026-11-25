---
title: Large language models and fine-tuning
summary: Understand how LLMs are trained and generate text, control sampling with temperature, and adapt a model cheaply with LoRA.
takeaways:
- An LLM is a transformer trained to predict the next token on a huge amount of text
- Temperature and sampling control how predictable or creative the output is
- Fine-tuning with LoRA trains tiny adapter matrices instead of the whole model
---
## What an LLM is

A **large language model** is a very large transformer (billions of parameters) trained on a huge amount of text with one simple goal: **predict the next token**. Given "The capital of France is", it learns that " Paris" is likely. Doing this for trillions of tokens teaches it grammar, facts, reasoning patterns and writing styles as a side effect.

| Stage | What happens |
| --- | --- |
| **1. Pretraining** | predict the next token on a vast text collection; the expensive stage (weeks on thousands of GPUs) |
| **2. Instruction tuning (fine-tuning)** | train on examples of questions and good answers so it follows instructions |
| **3. Alignment** | use human feedback (RLHF or related methods) so answers are helpful, honest and safe |
| **4. Use** | prompt it, or adapt it further for your task |

## How text is generated

The model outputs a **score for every token** in its vocabulary. A softmax turns the scores into probabilities. We pick one token, add it to the text, and repeat. The way we pick matters.

```python
import numpy as np

tokens = [" Paris", " Lyon", " France", " the", " pizza"]
logits = np.array([6.0, 4.0, 3.5, 2.0, 0.0])

def softmax_with_temperature(logits, temperature):
    scaled = logits / temperature
    e = np.exp(scaled - scaled.max())
    return e / e.sum()

print("next-token probabilities after 'The capital of France is'")
for temperature in (0.5, 1.0, 2.0):
    probs = softmax_with_temperature(logits, temperature)
    row = "  ".join(f"{t.strip()}:{p:.2f}" for t, p in zip(tokens, probs))
    print(f"temperature {temperature}: {row}")
```

```output
next-token probabilities after 'The capital of France is'
temperature 0.5: Paris:0.98  Lyon:0.02  France:0.01  the:0.00  pizza:0.00
temperature 1.0: Paris:0.81  Lyon:0.11  France:0.07  the:0.01  pizza:0.00
temperature 2.0: Paris:0.54  Lyon:0.20  France:0.16  the:0.07  pizza:0.03
```

**Temperature** reshapes the probabilities:

- **Low** temperature (0.5) makes the top choice dominate: predictable, factual, repetitive.
- **Temperature 1** uses the model's raw probabilities.
- **High** temperature (2.0) flattens the distribution, so unlikely words get a real chance: more creative, and more error-prone.

| Setting | Meaning |
| --- | --- |
| **greedy** | always pick the most likely token (temperature near 0) |
| **temperature** | sharpen or flatten the distribution |
| **top-k** | sample only from the k most likely tokens |
| **top-p (nucleus)** | sample from the smallest set of tokens whose probabilities add up to p (e.g. 0.9) |
| **max tokens, stop sequences** | control length |

```python
rng = np.random.default_rng(0)
probs = softmax_with_temperature(logits, 1.0)

greedy = tokens[int(np.argmax(probs))]
sampled = [tokens[rng.choice(len(tokens), p=probs)] for _ in range(8)]
print("greedy choice:", greedy)
print("8 sampled choices:", sampled)
```

```output
greedy choice:  Paris
8 sampled choices: [' Paris', ' Paris', ' Paris', ' Paris', ' Lyon', ' Lyon', ' Paris', ' Paris']
```

Greedy always says " Paris". Sampling usually does, but sometimes picks another plausible word. This randomness is why the same prompt can give different answers.

## Why LLMs make things up

An LLM predicts what text is **likely**, not what is **true**. When it lacks knowledge it still produces fluent, confident text: a **hallucination**. Reduce it with:

| Technique | Idea |
| --- | --- |
| **RAG** (retrieval-augmented generation) | search your own documents first and give the relevant passages to the model in the prompt |
| clear instructions and examples in the prompt | steer behaviour without training |
| asking for sources and verifying them | catch fabricated facts |
| fine-tuning on your domain | teach style, format and terminology |
| lower temperature | fewer wild guesses |

## Fine-tuning is expensive, unless you are clever

Fully fine-tuning a 7-billion-parameter model means storing gradients and optimiser state for **all** 7 billion weights, needing a lot of GPU memory. **LoRA (Low-Rank Adaptation)** avoids it: freeze the original weights and learn only a **small correction**, expressed as the product of two thin matrices.

For a weight matrix `W` of size 768 by 768, instead of updating all 589,824 numbers (590,592 with the bias), learn `A` (768 by r) and `B` (r by 768) with a tiny rank `r`, and use `W + A·B`:

```python
import torch
from torch import nn

class LoRALinear(nn.Module):
    def __init__(self, base: nn.Linear, rank=8, alpha=16):
        super().__init__()
        self.base = base
        for p in self.base.parameters():
            p.requires_grad = False                          # freeze the original weights
        self.A = nn.Parameter(torch.randn(base.in_features, rank) * 0.01)
        self.B = nn.Parameter(torch.zeros(rank, base.out_features))      # zeros: starts as exactly the original model
        self.scale = alpha / rank

    def forward(self, x):
        return self.base(x) + (x @ self.A @ self.B) * self.scale

torch.manual_seed(0)
base = nn.Linear(768, 768)
lora = LoRALinear(base, rank=8)

x = torch.randn(4, 768)
print("at the start, output equals the original layer's:", torch.allclose(lora(x), base(x)))

full = sum(p.numel() for p in base.parameters())
trainable = sum(p.numel() for p in lora.parameters() if p.requires_grad)
print(f"full fine-tuning would train {full:,} parameters")
print(f"LoRA trains {trainable:,} parameters ({100 * trainable / full:.1f}%)")
```

```output
at the start, output equals the original layer's: True
full fine-tuning would train 590,592 parameters
LoRA trains 12,288 parameters (2.1%)
```

Because `B` starts at zero, the adapted layer begins **identical** to the original, and training moves it gently away. LoRA trains about 2% of the parameters for this layer (and with a smaller rank, less), and for a full model the saved adapter is megabytes instead of many gigabytes. You can keep one big base model and many small adapters for different tasks.

## One training step touches only the adapter

```python
optimizer = torch.optim.Adam([p for p in lora.parameters() if p.requires_grad], lr=0.01)
target = torch.randn(4, 768)

before = base.weight.clone()
loss = nn.functional.mse_loss(lora(x), target)
optimizer.zero_grad()
loss.backward()
optimizer.step()

print("original weights unchanged:", torch.equal(before, base.weight))
print("adapter B changed         :", bool(lora.B.abs().sum() > 0))
```

```output
original weights unchanged: True
adapter B changed         : True
```

## The practical workflow

```py
pip install transformers peft datasets

from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model

model = AutoModelForCausalLM.from_pretrained("a-small-open-model")
config = LoraConfig(r=8, lora_alpha=16, target_modules=["q_proj", "v_proj"], lora_dropout=0.05)
model = get_peft_model(model, config)
model.print_trainable_parameters()          # typically well under 1% of all parameters
```

| Technique | Use when |
| --- | --- |
| **prompting** | the first thing to try; free, instant |
| **RAG** | the model needs your private or recent facts |
| **LoRA / QLoRA fine-tuning** | you need a specific style, format or behaviour, consistently |
| **full fine-tuning** | rarely; you have lots of data and compute |
| **training from scratch** | almost never, unless you are a large lab |

**QLoRA** also stores the frozen base model in 4-bit numbers, so a large model can be fine-tuned on a single consumer GPU.

:::tip
Try the cheapest options first: a better prompt, then retrieval (RAG), then fine-tuning. Most real applications are solved before reaching fine-tuning, and a clean, correct dataset matters far more than a clever training trick.
:::

:::interview
**Interviewers often ask:** "What is LoRA and why is it useful?" Low-Rank Adaptation freezes the pretrained weights and trains small low-rank matrices whose product is added to each weight matrix, so only a tiny fraction of parameters is trained. This cuts memory and storage dramatically while matching full fine-tuning quality on many tasks. "What does temperature do?" It scales the logits before the softmax: low temperature makes outputs more deterministic, high temperature makes them more diverse.
:::
