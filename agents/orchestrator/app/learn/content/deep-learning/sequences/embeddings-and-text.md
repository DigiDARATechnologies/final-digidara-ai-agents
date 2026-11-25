---
title: Embeddings and working with text
summary: Turn words into learned vectors with embeddings, understand tokenisation, and train a small text classifier.
takeaways:
- Neural networks need numbers, so text is split into tokens and each token becomes an embedding vector
- An embedding is a learnable lookup table; similar words end up with similar vectors
- Modern models use subword tokenisation so they can handle any word
---
## The problem: networks only read numbers

To feed text to a network we must convert words to numbers in a way that keeps meaning. Two steps:

1. **Tokenise**: split text into pieces (tokens) and give each a number (an index).
2. **Embed**: replace each index with a **vector** of numbers that the network learns.

## Why not one-hot vectors?

A **one-hot** vector for a 50,000-word vocabulary has 50,000 numbers, with a single 1. It is huge, and every word is equally different from every other ("good" is as far from "great" as from "banana"). An **embedding** is a short, dense vector (say 64 or 300 numbers) where **similar words get similar vectors**, learned from data.

## An embedding is a lookup table

```python
import torch
from torch import nn

torch.manual_seed(0)
vocab_size, dimension = 6, 3
embedding = nn.Embedding(vocab_size, dimension)

print("table shape:", tuple(embedding.weight.shape), "(one row per word, one column per dimension)")

word_ids = torch.tensor([2, 5])
print("vectors for words 2 and 5:", tuple(embedding(word_ids).shape))

# an embedding lookup is the same as one-hot times the table, only much faster
one_hot = nn.functional.one_hot(word_ids, vocab_size).float()
print("same as one-hot times the table:", torch.allclose(one_hot @ embedding.weight, embedding(word_ids)))
```

```output
table shape: (6, 3) (one row per word, one column per dimension)
vectors for words 2 and 5: (2, 3)
same as one-hot times the table: True
```

An embedding layer is a table with one learnable row per word. Looking up word number 2 simply returns row 2. During training the rows are adjusted by gradient descent like any other weights, so words used in similar contexts drift towards similar vectors.

## Similarity between vectors

We compare vectors with **cosine similarity**: 1 means pointing the same way, 0 unrelated, −1 opposite. Here are small **made-up** vectors, just to show the idea (real embeddings are learned):

```python
import numpy as np

vectors = {
    "king":   np.array([0.9, 0.8, 0.1]),
    "queen":  np.array([0.9, 0.7, 0.9]),
    "man":    np.array([0.1, 0.9, 0.1]),
    "banana": np.array([-0.7, 0.1, 0.6]),
}

def cosine(a, b):
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))

print("king vs queen :", round(cosine(vectors["king"], vectors["queen"]), 2))
print("king vs man   :", round(cosine(vectors["king"], vectors["man"]), 2))
print("king vs banana:", round(cosine(vectors["king"], vectors["banana"]), 2))
```

```output
king vs queen : 0.83
king vs man   : 0.74
king vs banana: -0.44
```

In real, trained embeddings (word2vec, GloVe, or those inside large language models), such directions capture meaning: related words are close, and relationships like king − man + woman ≈ queen appear as vector arithmetic.

## A tiny text classifier

We classify short movie comments as positive or negative. The model averages the embeddings of the words and feeds the average to a linear layer:

```python
import torch
from torch import nn

train_texts = [
    ("a great movie", 1), ("i love this film", 1), ("wonderful and fun", 1), ("excellent acting very good", 1),
    ("happy with this great film", 1), ("such a good movie", 1), ("i love it wonderful", 1), ("great fun excellent", 1),
    ("a terrible movie", 0), ("i hate this film", 0), ("awful and boring", 0), ("bad acting very boring", 0),
    ("sad and terrible film", 0), ("such a bad movie", 0), ("i hate it awful", 0), ("boring awful bad", 0),
]
test_texts = [
    ("this film was wonderful", 1), ("the movie was awful", 0), ("i love this great movie", 1),
    ("what a terrible boring film", 0), ("very good and fun", 1), ("bad bad film", 0),
]

words = sorted({w for text, _ in train_texts for w in text.split()})
index = {w: i + 1 for i, w in enumerate(words)}            # 0 is reserved for words never seen in training
print("vocabulary size:", len(index))

def encode(text):
    return torch.tensor([index.get(w, 0) for w in text.split()])

class TextClassifier(nn.Module):
    def __init__(self, vocab_size, dimension=8):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size + 1, dimension)
        self.head = nn.Linear(dimension, 1)

    def forward(self, ids):
        return self.head(self.embedding(ids).mean(dim=0))      # average the word vectors, then classify

torch.manual_seed(0)
model = TextClassifier(len(index))
optimizer = torch.optim.Adam(model.parameters(), lr=0.05)
loss_fn = nn.BCEWithLogitsLoss()

for epoch in range(60):
    for text, label in train_texts:
        loss = loss_fn(model(encode(text)), torch.tensor([float(label)]))
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

correct = 0
for text, label in test_texts:
    with torch.no_grad():
        probability = torch.sigmoid(model(encode(text))).item()
    correct += int((probability > 0.5) == bool(label))
    print(f"{probability:.2f}  {'positive' if probability > 0.5 else 'negative'}  <-  {text}")
print(f"test accuracy: {correct}/{len(test_texts)}")
```

```output
vocabulary size: 24
0.98  positive  <-  this film was wonderful
0.02  negative  <-  the movie was awful
1.00  positive  <-  i love this great movie
0.00  negative  <-  what a terrible boring film
1.00  positive  <-  very good and fun
0.00  negative  <-  bad bad film
test accuracy: 6/6
```

The model never saw these exact sentences, but it learned an embedding for each word, and sentences made of words like "wonderful" and "love" land on the positive side while "awful" and "boring" land on the negative side. This is a toy (16 training sentences, a very small vocabulary) but it is the genuine mechanism behind text classification.

## Tokenisation in real systems

Splitting on spaces breaks down: new words, typos, languages without spaces, huge vocabularies. Modern models use **subword** tokenisation, which splits rare words into pieces:

| Level | Example for "unhappiness" | Problem |
| --- | --- | --- |
| word | `unhappiness` | unknown if rare; the vocabulary is enormous |
| character | `u n h a p p i n e s s` | very long sequences, little meaning per token |
| **subword (BPE, WordPiece)** | `un` `happi` `ness` | **a good balance**: any word can be built from known pieces |

```py
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
print(tokenizer.tokenize("Tokenisation handles unhappiness"))
print(tokenizer("Hello world")["input_ids"])
```

## From embeddings to modern language models

| Stage | Idea |
| --- | --- |
| **static embeddings** (word2vec, GloVe) | one vector per word, whatever the context |
| **contextual embeddings** (ELMo, BERT, GPT) | the vector depends on the **sentence**, so "bank" in "river bank" differs from "bank" in "bank loan" |
| **transformers** (next lesson) | attention lets each word look at all the others to build its meaning |

:::tip
Always pad or truncate sequences to a fixed length when batching, and tell the model which positions are padding (a **mask**), or it will treat padding as real words. `nn.Embedding(..., padding_idx=0)` and attention masks handle this.
:::

:::interview
**Interviewers often ask:** "What is an embedding and why is it better than one-hot encoding?" An embedding maps each token to a short, dense, learnable vector. One-hot vectors are huge, sparse and treat all words as equally different, while embeddings are compact and place similar words near each other, so the network can generalise between them.
:::
