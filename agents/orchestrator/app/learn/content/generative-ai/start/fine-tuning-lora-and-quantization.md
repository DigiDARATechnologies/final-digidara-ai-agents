---
title: Fine-tuning, LoRA and quantization
summary: Learn when to fine-tune a model, how LoRA makes it cheap, how quantization shrinks models to run on small hardware, and what good training data looks like.
takeaways:
- Fine-tune to change behaviour and style, not to add changing facts (use RAG for facts)
- LoRA trains small add-on weights, so fine-tuning needs far less memory and cost
- Quantization stores weights in fewer bits so big models fit on small machines, with a small quality loss
---
## What fine-tuning really changes

Fine-tuning continues training a model on **your examples**. It is good at:

- a fixed **tone or format** (always answer as JSON, always in your brand voice)
- a narrow **task** (classify support tickets, extract fields from invoices)
- making a **small model** perform like a bigger one on one task

It is poor at adding facts that change. A fine-tuned model can still forget or invent facts. For facts, use **RAG**. Many strong systems use both.

## Full fine-tuning vs LoRA

A 7-billion-parameter model has 7 billion numbers. Training all of them needs very large GPU memory.

**LoRA (Low-Rank Adaptation)** freezes the original weights and trains two tiny matrices beside each large one. Their product is the "change". Only the tiny matrices are trained and saved.

| | Full fine-tuning | LoRA |
| --- | --- | --- |
| Weights trained | all | under 1 percent |
| GPU memory | very high | much lower |
| Saved file | whole new model | a small adapter (megabytes) |
| Switching tasks | load another model | swap the adapter |

**QLoRA** combines LoRA with a quantized base model, so a 7B model can be tuned on a single consumer GPU.

```python
from peft import LoraConfig, get_peft_model

config = LoraConfig(r=8, lora_alpha=16, target_modules=["q_proj", "v_proj"], lora_dropout=0.05)
model = get_peft_model(base_model, config)
model.print_trainable_parameters()   # a tiny share of all parameters
```

`r` is the size (rank) of the small matrices. A larger `r` can learn more but costs more.

## Training data matters most

- **Quality beats quantity**: a few hundred to a few thousand clean, consistent examples often work.
- Use the **same format** you will use in production (the same prompt layout).
- Include **hard and edge cases**, and examples of refusing correctly.
- Hold back 10 to 20 percent as a **test set** the model never trains on.
- Remove duplicates and anything private.

Bad examples teach bad habits. If your answers disagree with each other, the model learns to be inconsistent.

## Quantization

Weights are normally stored as 16-bit numbers. **Quantization** stores them in 8 or 4 bits.

| Format | Memory for a 7B model | Quality |
| --- | --- | --- |
| 16-bit | about 14 GB | best |
| 8-bit | about 7 GB | almost the same |
| 4-bit | about 3.5 GB | small drop, usually acceptable |

It trades a little accuracy for a model that is smaller and faster, which is how large models run on laptops and phones. Always test your task after quantizing.

## Decision guide

1. Try a better **prompt** with examples. Cheapest.
2. Add **RAG** if the model lacks your facts.
3. **Fine-tune** if you still need consistent behaviour or a cheaper, smaller model.

:::warning
Do not fine-tune on customer data without permission, and do not expect fine-tuning to remove hallucination. Test the tuned model against your held-out set before using it.
:::
