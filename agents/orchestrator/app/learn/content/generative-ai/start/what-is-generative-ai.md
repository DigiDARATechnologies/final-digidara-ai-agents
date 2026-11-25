---
title: What is generative AI?
summary: Understand what generative AI creates, how a language model works at its core (predicting the next token), and what it can and cannot do.
takeaways:
- Generative AI creates new content (text, images, code, audio) instead of only labelling existing data
- A language model works by predicting the next token, over and over
- It produces likely text, not guaranteed true text, so you must check its output
---
## From predicting to creating

Most machine learning you have seen so far **classifies or predicts**: spam or not spam, a house price. **Generative AI** **creates** new content that looks like the data it learned from.

| Type | Output | Examples |
| --- | --- | --- |
| **Text** | answers, emails, summaries, code | ChatGPT, Claude, Gemini |
| **Images** | pictures from a description | Stable Diffusion, DALL-E, Midjourney |
| **Audio** | speech, music | text-to-speech, voice cloning |
| **Video** | short clips | text-to-video models |
| **Code** | programs and fixes | coding assistants |

## The core idea: predict the next token

A **large language model (LLM)** is trained on huge amounts of text to do one simple job: given the text so far, **predict the next token** (a word or a piece of a word). To write a paragraph, it predicts one token, adds it to the text, and predicts again.

You can see the idea with a tiny model that just counts which word follows which:

```python
import random
from collections import Counter, defaultdict

text = """students learn python and students learn data science.
students build projects and students share projects.
good projects get good jobs and good jobs need good skills."""

words = text.replace(".", " .").split()
follows = defaultdict(Counter)
for current, nxt in zip(words, words[1:]):
    follows[current][nxt] += 1                       # count what comes after each word

print("after 'students':", dict(follows["students"]))
print("after 'good'    :", dict(follows["good"]))
```

```output
after 'students': {'learn': 2, 'build': 1, 'share': 1}
after 'good'    : {'projects': 1, 'jobs': 2, 'skills': 1}
```

Now generate by always picking the **most likely** next word (greedy), and then by **sampling** with some randomness:

```python
def generate(start, length, creative=False, seed=0):
    rng = random.Random(seed)
    output = [start]
    for _ in range(length):
        options = follows[output[-1]]
        if not options:
            break
        if creative:
            choices, weights = zip(*options.items())
            output.append(rng.choices(choices, weights=weights)[0])       # random, but favours common words
        else:
            output.append(options.most_common(1)[0][0])                   # always the most likely word
    return " ".join(output)

print("greedy  :", generate("students", 8))
print("sampled :", generate("students", 8, creative=True, seed=3))
print("sampled :", generate("students", 8, creative=True, seed=4))
```

```output
greedy  : students learn python and students learn python and students
sampled : students learn data science . good projects and good
sampled : students learn python and students learn python and good
```

The greedy version takes the same safe path every time, and here it even gets stuck in a loop ("students learn python and students learn python..."), a real weakness of always picking the top choice. Sampling gives variety. **Temperature** in a real LLM controls exactly this: low temperature is close to greedy and predictable, high temperature is more varied and more risky.

A real LLM does the same thing with a vastly better "next-word predictor": a **transformer** with billions of parameters, trained on trillions of tokens, that looks at the **whole** text so far (not just one word). That is why its output feels fluent and knowledgeable.

## What follows from "it predicts likely text"

| Strength | Why |
| --- | --- |
| fluent writing in any style | it learned patterns of language |
| explains, summarises, translates | these are patterns in text |
| writes and explains code | code is text with strong patterns |
| follows instructions | extra training on instructions and human feedback |

| Weakness | Why |
| --- | --- |
| **hallucination**: confident but false statements | it produces what is *likely*, not what is *true* |
| no knowledge after its training date | it only knows what it was trained on |
| weak at exact arithmetic and counting | it predicts text, it does not calculate |
| can repeat bias from its training data | it learned from human writing |
| cannot know your private data | unless you provide it (the RAG lesson) |

:::warning
Never copy an AI answer into homework, code that goes to production, or a medical, legal or money decision without checking it. A fluent, confident answer is not evidence that it is correct.
:::

## How a model like ChatGPT is made

| Stage | What happens |
| --- | --- |
| **1. Pre-training** | learn to predict the next token on a very large text collection (months of computing) |
| **2. Instruction tuning** | train on examples of questions and good answers so it follows instructions |
| **3. Alignment** | use human feedback so answers are helpful, honest and safer |
| **4. Your application** | prompt it, give it your documents (RAG), or give it tools (agents) |

This course teaches stage 4: how to **use** these models well. The deep learning course explains stages 1 to 3 in more depth.

:::interview
**Interviewers often ask:** "How does an LLM generate text?" It converts text into tokens, predicts a probability for every possible next token, picks one (greedily or by sampling), appends it and repeats. Temperature controls how random the choice is.
:::
