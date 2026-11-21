---
title: Word embeddings
summary: Understand how words become short vectors that capture meaning, so that similar words are close together, and when to use them.
takeaways:
- An embedding represents a word as a short list of numbers learned from how words are used
- Similar words get similar vectors, which Bag of Words cannot do
- Today most NLP uses pretrained embeddings or transformer models instead of training from scratch
---
## The idea

In Bag of Words, "great" and "excellent" are two unrelated columns. But people use them in the same situations. An **embedding** gives each word a short vector (for example 100 numbers) learned from the contexts where the word appears, so **words used in similar ways get similar vectors.**

> "You shall know a word by the company it keeps." (J. R. Firth)

## Similar words are close

Real embeddings are learned, but the idea is easy to see with a few made-up numbers. Cosine similarity measures how close two vectors point:

```python
import numpy as np

vectors = {                       # made-up vectors, only to show the idea
    "great":     np.array([0.9, 0.8, 0.1]),
    "excellent": np.array([0.85, 0.9, 0.15]),
    "terrible":  np.array([-0.8, -0.7, 0.2]),
    "table":     np.array([0.0, 0.1, 0.95]),
}

def cosine(a, b):
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))

print("great vs excellent:", round(cosine(vectors["great"], vectors["excellent"]), 2))
print("great vs terrible :", round(cosine(vectors["great"], vectors["terrible"]), 2))
print("great vs table    :", round(cosine(vectors["great"], vectors["table"]), 2))
```

```output
great vs excellent: 1.0
great vs terrible : -0.96
great vs table    : 0.15
```

"great" and "excellent" point the same way (close to 1), "terrible" points the opposite way (negative), and "table" is unrelated (near 0). A sentiment model can now generalise: if it learned that "great" is positive, it also treats "excellent" as positive, even if it never saw that word in training.

## How embeddings are learned

**Word2Vec** (2013) trains a small network to predict a word from its neighbours (or neighbours from a word). The network's internal weights for each word become its embedding.

| Method | Idea |
| --- | --- |
| **Word2Vec** | predict neighbouring words; fast and simple |
| **GloVe** | use counts of how often words appear together |
| **FastText** | also uses pieces of words, so it handles new words and spelling errors |
| **Contextual** (BERT, GPT) | the vector depends on the **sentence**, so "bank" of a river and "bank" for money differ |

## Using Word2Vec

```py
pip install gensim

from gensim.models import Word2Vec

sentences = [["the", "delivery", "was", "fast"], ["great", "packing", "and", "fast", "delivery"]]   # a list of token lists
model = Word2Vec(sentences, vector_size=100, window=5, min_count=1, epochs=50)

print(model.wv["delivery"].shape)                 # (100,)
print(model.wv.most_similar("fast", topn=3))      # the closest words
```

Word2Vec needs a **lot** of text (millions of words) to be useful. With a tiny corpus the vectors are meaningless, so in practice you load **pretrained** vectors:

```py
import gensim.downloader as api
glove = api.load("glove-wiki-gigaword-100")          # pretrained on Wikipedia
print(glove.most_similar("king", topn=3))
```

## Sentences and documents

To get one vector for a whole sentence, the simplest method is to **average** the word vectors. Better methods use sentence-embedding models:

```py
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("all-MiniLM-L6-v2")                # a small, popular model
vectors = model.encode(["How do I reset my password?", "I forgot my login"])
```

Sentences that mean the same thing get nearby vectors even with no words in common, which is how modern semantic search and chatbots find the right answer.

## Which representation to use

| Approach | Strength | Weakness |
| --- | --- | --- |
| **Bag of Words, TF-IDF** | simple, fast, works well with small data | no meaning, big sparse vectors |
| **Word2Vec, GloVe** | captures word similarity, small dense vectors | one vector per word, whatever the context |
| **Transformer embeddings** | understands context and whole sentences | needs more compute, a pretrained model |

:::tip
For a first project, start with TF-IDF and logistic regression: it trains in seconds and is a strong baseline. Move to embeddings or transformers only if the baseline is not good enough.
:::

:::interview
**Interviewers often ask:** "What is a word embedding and why is it better than one-hot or Bag of Words?" A dense, low-dimensional vector learned from word usage, so similar words are close together. One-hot and Bag of Words treat every word as completely unrelated and give huge sparse vectors.
:::
