---
title: How transformers work
summary: Understand the idea behind every modern LLM: attention lets each word look at the other words, and stacked layers turn that into a prediction of the next token.
takeaways:
- Attention lets every token decide which other tokens matter for its meaning
- A transformer is many layers of attention plus small neural networks, ending in a next-token prediction
- Training predicts the next token on huge text; fine-tuning and feedback then make the model helpful
---
## The problem attention solves

Read this sentence: "The trophy did not fit in the suitcase because **it** was too big." What does "it" mean? You look back at the other words and decide it means the trophy. Older models read words one by one and forgot early words. The **transformer** (2017) lets every word look at **all** the other words at once and decide which ones matter. This is called **attention**.

## Attention in one picture

For each token the model builds three things from its embedding:

| Name | Think of it as | Job |
| --- | --- | --- |
| **Query** | "what am I looking for?" | the token asking the question |
| **Key** | "what do I contain?" | the label other tokens are matched against |
| **Value** | "what I hand over" | the information that is passed on |

The query of "it" is compared with the key of every other token. Tokens with a high match (trophy) get a high **attention weight**, and their values are blended into the new meaning of "it".

:::formula Attention
`Attention(Q, K, V) = softmax(Q·Kᵀ / √d) · V`

Score every pair, turn the scores into weights that add to 1 (softmax), then take a weighted mix of the values.
:::

A real model runs many attention **heads** in parallel. One head may track grammar, another may track who "it" refers to.

## The full transformer block

```text
tokens -> embeddings (+ position information)
   repeat N times (12 to 100+ layers):
        self-attention   (tokens look at each other)
        feed-forward net (each token is processed on its own)
   -> probabilities for the next token
```

- **Position information** is added because attention alone does not know word order.
- **Decoder-only** models (GPT, Claude, Llama) only look at earlier tokens, so they can generate text left to right.
- **Encoder** models (BERT) look at both sides and are good for understanding tasks such as classification and search.

## Generating text

The model outputs a probability for every token in its vocabulary. One token is chosen (the sampling lesson controls how), appended, and the whole process repeats. This is why long answers take longer: **one token per step**.

Because attention compares every token with every other token, cost grows quickly with length. This is the reason **context windows have a limit** and long prompts cost more.

## How a model is trained

1. **Pre-training**: predict the next token on trillions of words of text. This is where it learns language and facts. It is very expensive, so only a few companies do it.
2. **Instruction tuning**: train on examples of questions with good answers, so it follows instructions.
3. **Preference tuning (RLHF and similar)**: humans rank answers and the model is nudged toward the preferred ones. This makes it more helpful and safer.

:::note Why models hallucinate
The model is trained to produce **likely** text, not **verified** text. If it does not know, a fluent but wrong answer is still "likely". This is why we add retrieval and checks.
:::

:::remember
Attention = every token looks at every other token and decides what matters. Stack many layers, predict the next token, repeat. That is an LLM.
:::
