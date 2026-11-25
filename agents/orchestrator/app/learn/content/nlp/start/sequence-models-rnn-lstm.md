---
title: Sequence models: RNN and LSTM for text
summary: Understand why order matters in language, how recurrent networks read text step by step, and why they were replaced by transformers.
takeaways:
- Word order changes meaning, so bag-of-words loses information
- An RNN reads one word at a time and carries a memory (hidden state)
- RNNs forget long-range context and are slow to train, which transformers solved
---
## Order matters

"Dog bites man" and "Man bites dog" have the **same words** but opposite meaning. A bag-of-words model sees them as identical. We need models that read text **in order**.

## Recurrent neural networks (RNN)

An **RNN** reads one word at a time. After each word it updates a **hidden state**, a vector that acts as its memory of everything read so far, and passes it to the next step.

```text
   h0 -> [word 1] -> h1 -> [word 2] -> h2 -> [word 3] -> h3 -> prediction
```

The same small network (same weights) is reused at every step, so it handles any sentence length.

## The problem: forgetting

When the sentence is long, the signal from early words fades as it passes through many steps (the **vanishing gradient** problem). In "The **trophy** did not fit in the suitcase because **it** was too big", the model must remember "trophy" across many words.

## LSTM and GRU

An **LSTM** (long short-term memory) adds **gates** that decide what to keep, what to forget and what to output, so important information can travel further. A **GRU** is a lighter version with fewer gates. They were the standard for NLP from about 2014 to 2018.

```python
import torch.nn as nn

class TextClassifier(nn.Module):
    def __init__(self, vocab_size, embed_dim=64, hidden=64, classes=2):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embed_dim)
        self.lstm = nn.LSTM(embed_dim, hidden, batch_first=True)
        self.out = nn.Linear(hidden, classes)

    def forward(self, token_ids):
        vectors = self.embed(token_ids)        # words -> vectors
        _, (hidden, _) = self.lstm(vectors)    # read the sequence
        return self.out(hidden[-1])            # last memory -> label
```

(Shape only; the deep learning course covers training.)

## Seq2seq and attention

For translation, one RNN **encodes** the sentence into a vector and another **decodes** it into the new language. Squeezing a whole sentence into one vector loses detail, so **attention** was added: the decoder looks back at **all** the input words and focuses on the relevant ones. Attention turned out to be so powerful that it replaced the RNN entirely.

## Why transformers replaced RNNs

| | RNN / LSTM | Transformer |
| --- | --- | --- |
| Reads | one word at a time | all words at once |
| Training speed | slow (cannot parallelise) | fast on GPUs |
| Long-range context | weak | strong (attention) |
| Result | decent | state of the art |

You rarely build RNNs for new projects today, but they are still asked about in interviews and are useful for small sequence tasks such as sensor and time-series data.

:::interview Why do LSTMs work better than simple RNNs?
Gates let an LSTM keep important information across many steps and forget the rest, which reduces the vanishing gradient problem that makes simple RNNs forget long-range context.
:::
