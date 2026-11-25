---
title: Running models locally: Ollama and open models
summary: Run an open LLM on your own computer for privacy, learning and low cost, and understand the hardware needed.
takeaways:
- Open-weight models can run on your laptop with tools like Ollama
- Memory (RAM or VRAM) decides which model size you can run
- Local models trade some quality for privacy, control and zero per-token cost
---
## Why run locally

- **Privacy**: text never leaves your machine.
- **Cost**: no per-token fee once you have the hardware.
- **Offline** work and **full control** over the model.
- Great for **learning** and for prototypes.

The trade-off: smaller models are less capable than the biggest hosted ones, and you manage the hardware.

## Ollama: the easiest way

**Ollama** downloads and runs open models with one command.

```bash
ollama pull llama3.2          # download a small model
ollama run llama3.2           # chat in the terminal
```

It also starts a local server, so your code can call it like an API.

```python
import requests

reply = requests.post(
    "http://localhost:11434/api/generate",
    json={"model": "llama3.2", "prompt": "Explain recursion in two sentences.", "stream": False},
    timeout=120,
)
print(reply.json()["response"])
```

Other tools: **LM Studio** (a desktop app), **llama.cpp** (the fast C++ engine behind many tools), **vLLM** (high-throughput serving on servers).

## Hardware: how much memory?

A model's size is its number of **parameters**. Memory needed is roughly `parameters x bytes per weight`.

| Model size | 16-bit | 4-bit quantized | Runs on |
| --- | --- | --- | --- |
| 1B to 3B | 2 to 6 GB | 1 to 2 GB | ordinary laptop |
| 7B to 8B | 14 to 16 GB | 4 to 5 GB | laptop with 16 GB RAM |
| 13B | 26 GB | 8 GB | gaming GPU or Mac with 16 GB+ |
| 70B | 140 GB | 40 GB | high-end GPU or server |

**Quantization** (the fine-tuning lesson) shrinks the weights to 4 or 8 bits, which is why a 7B model fits on a normal laptop. Models run on CPU (slowly) or GPU (fast). The memory on the **GPU (VRAM)** is the usual limit.

## Choosing a local model

| Task | Try |
| --- | --- |
| general chat on a laptop | a 3B to 8B instruction-tuned model |
| coding help | a code-focused model |
| embeddings for RAG | a small embedding model (runs fast on CPU) |
| other languages | a multilingual model |

Always use the **instruct / chat** version for conversation, not the raw base model.

## Use it in your apps

A local server lets you build the same RAG and agent apps as with a hosted API, for free and privately. Many libraries (LangChain, LlamaIndex) can talk to Ollama.

## Limits to know

- Slower than hosted models on modest hardware.
- Less accurate on hard reasoning and long contexts.
- Good for **prototypes, private data and learning**; for production at scale you will host on GPUs or use an API.

:::tip
Install Ollama and try a small model today. Seeing a model run on your own machine makes everything in this course more real.
:::
