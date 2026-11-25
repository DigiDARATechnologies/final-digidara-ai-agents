---
title: Sampling: temperature, top-k and top-p
summary: See how an LLM turns scores into the next word, and how temperature, top-k and top-p change creativity and reliability.
takeaways:
- The model gives a probability to every possible next token
- Temperature sharpens or flattens the probabilities
- Top-k and top-p cut off unlikely tokens before choosing
---
## From scores to a choice

At each step the model outputs a score (**logit**) for every token. **Softmax** turns scores into probabilities, and one token is chosen. How we choose changes the style of the output.

Suppose the model is completing "The weather today is ..." and gives these scores:

```python
import math

tokens = ["sunny", "cloudy", "rainy", "purple", "banana"]
logits = [4.0, 3.0, 2.0, 0.0, -1.0]

def softmax(scores, temperature=1.0):
    scaled = [s / temperature for s in scores]
    biggest = max(scaled)
    exps = [math.exp(s - biggest) for s in scaled]
    total = sum(exps)
    return [e / total for e in exps]

for t in (0.2, 1.0, 2.0):
    probs = softmax(logits, t)
    print(f"temperature {t}:", {w: round(p, 3) for w, p in zip(tokens, probs)})
```

```output
temperature 0.2: {'sunny': 0.993, 'cloudy': 0.007, 'rainy': 0.0, 'purple': 0.0, 'banana': 0.0}
temperature 1.0: {'sunny': 0.654, 'cloudy': 0.241, 'rainy': 0.089, 'purple': 0.012, 'banana': 0.004}
temperature 2.0: {'sunny': 0.456, 'cloudy': 0.277, 'rainy': 0.168, 'purple': 0.062, 'banana': 0.037}
```

## Temperature

| Temperature | Effect | Use for |
| --- | --- | --- |
| **0 to 0.3** | almost always the top choice (sharp) | facts, code, extraction, classification |
| **0.7 to 1.0** | balanced variety | chat, writing |
| **1.2 and above** | flat, adventurous, can become nonsense | brainstorming (carefully) |

At low temperature "sunny" wins nearly every time. At high temperature "banana" gets a real chance. Temperature 0 is called **greedy** decoding: always the top token, so the output is (almost) repeatable.

## Top-k

Keep only the **k most likely** tokens, then choose among them. With `k = 3`, only sunny, cloudy and rainy remain.

## Top-p (nucleus sampling)

Keep the smallest group of tokens whose probabilities **add up to p**. If `p = 0.9`, add tokens from most to least likely until the total reaches 0.9, and ignore the rest. The group size adapts: few tokens when the model is confident, more when it is unsure.

```python
def top_p_tokens(probs, p):
    ranked = sorted(zip(tokens, probs), key=lambda x: x[1], reverse=True)
    kept, total = [], 0.0
    for word, prob in ranked:
        kept.append(word)
        total += prob
        if total >= p:
            break
    return kept

probs = softmax(logits, 1.0)
print(top_p_tokens(probs, 0.9))
print(top_p_tokens(probs, 0.6))
```

```output
['sunny', 'cloudy', 'rainy']
['sunny']
```

## Other settings

| Setting | Meaning |
| --- | --- |
| `max_tokens` | stop after this many tokens |
| `stop` sequences | stop when this text appears |
| frequency / presence penalty | discourage repeating words |
| `seed` | try to make runs repeatable (not always guaranteed) |

## Practical guidance

- For **accuracy** tasks (extract fields, write SQL, answer from documents): temperature **0 to 0.2**.
- For **creative** tasks: **0.7 to 1.0**.
- Change **temperature or top-p, not both** at the same time.
- Even at temperature 0, outputs can vary slightly between runs, so test with a set of examples rather than one.

:::remember
Low temperature = reliable and repeatable. High temperature = varied and risky. Match it to the task.
:::
