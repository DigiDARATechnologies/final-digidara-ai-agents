---
title: Bag of Words and TF-IDF
summary: Turn text into numbers by counting words, then improve the counts with TF-IDF so that rare, informative words count more.
takeaways:
- Bag of Words counts how often each word appears, ignoring order
- TF-IDF gives more weight to words that are frequent in one document but rare overall
- Both turn a document into a vector, so similarity and classification become possible
---
## From text to numbers

A model needs numbers. The simplest idea: build a **vocabulary** of all the words, then describe each document by **how many times each word appears**. Word order is thrown away (hence "bag").

```python
from sklearn.feature_extraction.text import CountVectorizer

docs = [
    "the delivery was fast",
    "the delivery was late",
    "fast delivery and great packing",
    "late and damaged product",
]

vectorizer = CountVectorizer()
counts = vectorizer.fit_transform(docs)

print("vocabulary:", list(vectorizer.get_feature_names_out()))
print("matrix shape (documents, words):", counts.shape)
print(counts.toarray())
```

```output
vocabulary: ['and', 'damaged', 'delivery', 'fast', 'great', 'late', 'packing', 'product', 'the', 'was']
matrix shape (documents, words): (4, 10)
[[0 0 1 1 0 0 0 0 1 1]
 [0 0 1 0 0 1 0 0 1 1]
 [1 0 1 1 1 0 1 0 0 0]
 [1 1 0 0 0 1 0 1 0 0]]
```

Each row is one document and each column one word. The matrix is mostly zeros, so libraries store it in a compact "sparse" form.

## The problem with raw counts

Common words appear in almost every document and dominate the counts, yet they say little ("the", "delivery" here). Rare words such as "damaged" are far more informative.

## TF-IDF: weight the informative words

**TF-IDF** has two parts:

| Part | Meaning |
| --- | --- |
| **TF** (term frequency) | how often the word appears **in this document** |
| **IDF** (inverse document frequency) | how **rare** the word is across all documents (rare means a high value) |

`TF-IDF = TF × IDF`. A word scores high when it is frequent here **and** rare elsewhere.

```python
from sklearn.feature_extraction.text import TfidfVectorizer
import pandas as pd

tfidf = TfidfVectorizer()
weights = tfidf.fit_transform(docs)

table = pd.DataFrame(weights.toarray(), columns=tfidf.get_feature_names_out()).round(2)
print(table.to_string())
```

```output
    and  damaged  delivery  fast  great  late  packing  product   the   was
0  0.00     0.00      0.42  0.52   0.00  0.00     0.00     0.00  0.52  0.52
1  0.00     0.00      0.42  0.00   0.00  0.52     0.00     0.00  0.52  0.52
2  0.41     0.00      0.33  0.41   0.52  0.00     0.52     0.00  0.00  0.00
3  0.44     0.56      0.00  0.00   0.00  0.44     0.00     0.56  0.00  0.00
```

In the fourth document, "damaged" and "product" (which appear nowhere else) get the **highest** weights, while "and" and "late" (shared with other documents) get less. TF-IDF automatically highlights what makes each document special.

## Similarity between documents

Because documents are now vectors, we can measure how alike they are with **cosine similarity** (1 is identical direction, 0 is nothing in common).

```python
from sklearn.metrics.pairwise import cosine_similarity

similarity = cosine_similarity(weights)
print(pd.DataFrame(similarity, columns=[f"doc{i}" for i in range(4)], index=[f"doc{i}" for i in range(4)]).round(2).to_string())
```

```output
      doc0  doc1  doc2  doc3
doc0  1.00  0.73  0.36  0.00
doc1  0.73  1.00  0.14  0.23
doc2  0.36  0.14  1.00  0.18
doc3  0.00  0.23  0.18  1.00
```

Documents 0 and 1 ("the delivery was fast" and "the delivery was late") are the most similar pair. Search engines and FAQ chatbots use exactly this idea.

## Useful options

| Option | Effect |
| --- | --- |
| `stop_words="english"` | drop common words |
| `ngram_range=(1, 2)` | also count **pairs** of words ("not good") |
| `min_df=2` | ignore words that appear in fewer than 2 documents |
| `max_features=5000` | keep only the 5,000 most frequent words |

```python
pairs = TfidfVectorizer(ngram_range=(1, 2)).fit(["not good at all", "very good indeed"])
print(sorted(pairs.get_feature_names_out()))
```

```output
['all', 'at', 'at all', 'good', 'good at', 'good indeed', 'indeed', 'not', 'not good', 'very', 'very good']
```

Word **pairs** capture a little of the word order that a plain bag throws away: "not good" is now its own feature, separate from "good".

## Limits

| Limit | Meaning |
| --- | --- |
| no order or grammar | "dog bites man" and "man bites dog" look the same without bigrams |
| no meaning | "great" and "excellent" are completely different columns |
| huge, sparse vectors | one column per word |

The next lesson, **word embeddings**, fixes the second problem.

:::interview
**Interviewers often ask:** "What is TF-IDF?" A score that multiplies how often a word appears in a document (TF) by how rare the word is across all documents (IDF), so frequent-in-this-document but rare-overall words get the most weight.
:::
