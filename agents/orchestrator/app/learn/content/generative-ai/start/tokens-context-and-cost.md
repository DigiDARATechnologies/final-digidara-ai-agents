---
title: Tokens, context windows and cost
summary: Learn the practical numbers behind every LLM call: tokens, the context window, the settings that change the output, and how to estimate cost.
takeaways:
- Models read and write tokens, not words; usage and cost are counted in tokens
- The context window is the model's working memory for one conversation
- Temperature, max tokens and stop settings shape the answer
---
## Tokens

An LLM does not see letters or words. Text is split into **tokens**: whole common words, parts of rarer words, punctuation. As a rough guide for English, **1 token is about 4 characters or three-quarters of a word**. Other languages often need **more tokens** for the same meaning, which makes them costlier and uses more of the context.

```python
def rough_tokens(text):
    return max(1, round(len(text) / 4))             # a rough English rule of thumb: 4 characters per token

samples = {
    "a short question": "What is gradient descent?",
    "a paragraph": "Gradient descent is an algorithm that repeatedly moves the weights a small step against the gradient of the loss, so the loss becomes smaller over time.",
}
for name, text in samples.items():
    print(f"{name:<18} {len(text):>4} characters  ->  about {rough_tokens(text):>3} tokens, {len(text.split()):>3} words")
```

```output
a short question     25 characters  ->  about   6 tokens,   4 words
a paragraph         152 characters  ->  about  38 tokens,  26 words
```

This is only an estimate. Each provider has an official tokeniser (for example the `tiktoken` library for OpenAI models) for exact counts.

## The context window

The **context window** is the maximum number of tokens a model can handle in one request: your instructions, the conversation so far, any documents you paste in, **and** its answer. Everything must fit.

| Idea | Meaning |
| --- | --- |
| a **small** window | the model forgets the start of a long conversation |
| a **large** window | you can include whole documents, but it costs more and is slower |
| "lost in the middle" | models can pay less attention to facts buried in the middle of very long inputs |

```python
window = 8000                       # tokens, an example size
reply_space = 1000                  # keep room for the answer
instructions = rough_tokens("You are a helpful study assistant. Answer briefly and use simple words. " * 3)
history = 2500                      # earlier messages

room_for_documents = window - reply_space - instructions - history
print("tokens left for documents:", room_for_documents)
print("roughly this many pages of text (about 500 tokens a page):", room_for_documents // 500)
```

```output
tokens left for documents: 4446
roughly this many pages of text (about 500 tokens a page): 8
```

Budgeting like this is the first step of designing any LLM application.

## Settings you can change

| Setting | Effect | Typical use |
| --- | --- | --- |
| **temperature** | randomness (0 is nearly the same answer each time, higher is more varied) | low for facts and code, higher for brainstorming |
| **top-p** | sample only from the most likely words that add up to p | an alternative way to control variety |
| **max tokens** | the longest answer allowed | control cost and length |
| **stop sequences** | text at which the model must stop | cut off structured output cleanly |
| **system prompt** | standing instructions for the whole conversation | role, tone, rules |

Even at temperature 0, outputs can vary slightly, so never build code that needs exactly the same words every time.

## Cost

You pay for **input tokens** (what you send) and **output tokens** (what you receive), usually priced per million tokens, with output costing more. Prices change, so always read the provider's current price list. The numbers below are made up to show the calculation:

```python
price_per_million_input = 3.00        # example price in dollars, NOT a real quote
price_per_million_output = 15.00

def call_cost(input_tokens, output_tokens):
    return input_tokens / 1_000_000 * price_per_million_input + output_tokens / 1_000_000 * price_per_million_output

one_call = call_cost(input_tokens=2_000, output_tokens=500)
print(f"one call   : ${one_call:.4f}")
print(f"10,000 calls a month: ${one_call * 10_000:,.2f}")

smaller_input = call_cost(input_tokens=500, output_tokens=500)
print(f"if we shorten the input to 500 tokens: ${smaller_input * 10_000:,.2f} a month")
```

```output
one call   : $0.0135
10,000 calls a month: $135.00
if we shorten the input to 500 tokens: $90.00 a month
```

A small cost per call becomes a real bill at scale. Ways to reduce it:

| Method | Saving |
| --- | --- |
| shorter prompts and fewer pasted documents | fewer input tokens |
| ask for concise answers, set max tokens | fewer output tokens |
| use a smaller, cheaper model for easy tasks | lower price per token |
| **caching** repeated prompt prefixes (many providers support it) | cheaper repeated input |
| retrieve only the relevant chunks (RAG) | send less text |

:::tip
Start every project with a rough budget: tokens per call, calls per day, price per token. It decides which model and design you can afford.
:::
