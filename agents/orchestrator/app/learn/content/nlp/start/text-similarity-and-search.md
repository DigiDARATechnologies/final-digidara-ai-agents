---
title: Text similarity and search
summary: Measure how close two texts are with cosine similarity and build a simple search engine over documents.
takeaways:
- Texts become vectors; similar texts have vectors pointing the same way
- Cosine similarity compares the direction of two vectors, ignoring length
- TF-IDF search ranks documents by similarity to the query
---
## From text to numbers

To compare texts we turn each into a **vector** (the TF-IDF lesson). Texts that use similar words get similar vectors.

## Cosine similarity

**Cosine similarity** measures the angle between two vectors: 1 means the same direction (very similar), 0 means unrelated.

:::formula Cosine similarity
`cos(a, b) = (a . b) / (|a| x |b|)`

Length does not matter, only direction. A long and a short document on the same topic still score high.
:::

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

docs = [
    "python is a popular programming language for data science",
    "machine learning models learn patterns from data",
    "the cricket team won the match by five wickets",
    "football and cricket are popular sports in india",
]

vectorizer = TfidfVectorizer(stop_words="english")
matrix = vectorizer.fit_transform(docs)

scores = cosine_similarity(matrix)
print(scores.round(2))
```

```output
[[1.   0.11 0.   0.13]
 [0.11 1.   0.   0.  ]
 [0.   0.   1.   0.14]
 [0.13 0.   0.14 1.  ]]
```

The diagonal is 1 because each text is identical to itself. Documents 2 and 3 (both cricket) score 0.14 and documents 0 and 1 (both data) score 0.11. These numbers are small because the texts share very few words. Documents 0 and 3 score 0.13 only because they share the word "popular", which shows the weakness of matching words: it can link unrelated texts, and miss related ones that use different words.

## A tiny search engine

Turn the **query** into a vector with the same vectorizer and rank documents by similarity.

```python
def search(query, top=2):
    query_vector = vectorizer.transform([query])
    similarity = cosine_similarity(query_vector, matrix).ravel()
    ranked = similarity.argsort()[::-1][:top]
    return [(round(float(similarity[i]), 2), docs[i]) for i in ranked]

for score, text in search("learn data science with python"):
    print(score, text)
print()
for score, text in search("who won the cricket match"):
    print(score, text)
```

```output
0.6 python is a popular programming language for data science
0.36 machine learning models learn patterns from data

0.75 the cricket team won the match by five wickets
0.19 football and cricket are popular sports in india
```

This is how classic search works. Its weakness: it only matches **shared words**. A query like "football score" would not match a document about "soccer result". **Embeddings** (the next lessons and the Generative AI course) fix this by comparing **meaning**.

## Other similarity measures

| Measure | Idea | Use |
| --- | --- | --- |
| **Cosine** | angle between vectors | documents, embeddings |
| **Jaccard** | shared words / all words | quick overlap of two sets |
| **Edit distance** | letter changes needed | spelling, fuzzy matching |

```python
def jaccard(a, b):
    a, b = set(a.split()), set(b.split())
    return len(a & b) / len(a | b)

print(round(jaccard("the cat sat on the mat", "the cat lay on the rug"), 2))
```

```output
0.43
```

## Uses

Duplicate detection, "similar articles", FAQ matching, plagiarism checking, recommendation by description.

:::remember
Vectorise, then compare with cosine similarity. Word-count vectors find shared words; embedding vectors find shared meaning.
:::
