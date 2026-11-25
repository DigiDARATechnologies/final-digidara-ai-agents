---
title: The LLM landscape: choosing a model
summary: Compare closed and open models, sizes, context windows and cost, and learn a simple way to pick the right model for a task.
takeaways:
- Models differ in quality, speed, cost, context length and licence
- Open-weight models can run on your own hardware; hosted models are easier
- Choose by testing on your own examples, not by leaderboard rank alone
---
## Many models, one idea

All the big names (Claude, GPT, Gemini, Llama, Mistral, Qwen, DeepSeek and more) are transformer language models. They differ in the things that matter for a product.

## What to compare

| Factor | Question to ask |
| --- | --- |
| **Quality** | Does it solve **my** task correctly? |
| **Speed (latency)** | How fast is the first token and the full answer? |
| **Cost** | Price per million input and output tokens |
| **Context window** | How much text fits in one call? |
| **Modalities** | Text only, or images, audio, files too? |
| **Tool and JSON support** | Reliable function calling and structured output? |
| **Privacy and licence** | Where does the data go? Can I use it commercially? |

## Closed (hosted) vs open-weight

| | Hosted API (closed) | Open-weight model |
| --- | --- | --- |
| Examples | Claude, GPT, Gemini | Llama, Mistral, Qwen, Gemma |
| Setup | an API key | you host it (GPU) or use a host |
| Quality at the top end | usually highest | close behind, improving fast |
| Data leaves your servers | yes (to the provider) | no, if self-hosted |
| Cost shape | pay per token | fixed hardware cost |
| Customisation | prompts, some fine-tuning | full fine-tuning possible |

"Open-weight" means you can download the model; the licence still matters, so read it.

## Size tiers

Providers usually offer a **small/fast/cheap**, a **balanced**, and a **large/best** model.

| Tier | Use for |
| --- | --- |
| Small | classification, extraction, simple chat, high volume |
| Medium | most apps: assistants, RAG, summaries |
| Large / reasoning | hard coding, analysis, multi-step planning |

A reasoning model "thinks" before answering, so it is slower and costs more, but is better on hard problems.

## How to choose: a simple process

1. Write **20 to 50 real examples** of your task with good answers.
2. Run them on a **small**, a **medium** and a **large** model.
3. Score the results (the evaluation lesson).
4. Pick the **cheapest model that passes**. Many tasks do not need the biggest model.
5. Re-test when new models appear; this field changes every few months.

## Route by difficulty

Use a cheap model for easy requests and a stronger one for hard requests. A first cheap call can even decide how hard the question is.

:::tip
Avoid being locked in: call the model through one small function in your code, so changing the provider means changing one place.
:::
