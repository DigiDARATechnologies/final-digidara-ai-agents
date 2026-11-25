---
title: Topic modeling
summary: Discover the hidden themes in a pile of documents without labels, using NMF (and LDA).
takeaways:
- Topic modeling is unsupervised: it finds themes without labelled data
- Each topic is a group of words that appear together; each document mixes topics
- You choose the number of topics and judge them by reading the top words
---
## The problem

You have 10,000 customer reviews or news articles and no labels. What are people talking about? **Topic modeling** groups words that often appear together into **topics**, and tells you which topics each document contains.

Popular methods: **LDA** (Latent Dirichlet Allocation) and **NMF** (non-negative matrix factorisation). Newer tools such as BERTopic use embeddings.

## Example with NMF

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import NMF

docs = [
    "the team won the cricket match with a late wicket",
    "the batsman scored a century in the final match",
    "the bowler took five wickets and the team won the series",
    "the new phone has a faster processor and a better camera",
    "this laptop battery lasts long and the screen is bright",
    "the camera and battery of the phone impressed reviewers",
    "the election results were announced and the minister spoke",
    "parliament passed the new bill after a long debate",
    "the minister promised new policy on education in parliament",
]

vectorizer = TfidfVectorizer(stop_words="english")
matrix = vectorizer.fit_transform(docs)

model = NMF(n_components=3, random_state=0, init="nndsvd")
weights = model.fit_transform(matrix)          # document x topic
words = vectorizer.get_feature_names_out()

for number, topic in enumerate(model.components_):
    top_words = [words[i] for i in topic.argsort()[::-1][:5]]
    print(f"Topic {number}:", ", ".join(top_words))
```

```output
Topic 0: camera, phone, battery, impressed, reviewers
Topic 1: won, team, match, late, cricket
Topic 2: parliament, new, minister, debate, passed
```

Reading the top words, we can **name** the topics ourselves: sports, gadgets, politics. The algorithm only finds the word groups; naming them is a human job.

## Which topic is each document about?

```python
for doc, row in zip(docs, weights):
    print(row.argmax(), doc[:45])
```

```output
1 the team won the cricket match with a late wi
1 the batsman scored a century in the final mat
1 the bowler took five wickets and the team won
0 the new phone has a faster processor and a be
0 this laptop battery lasts long and the screen
0 the camera and battery of the phone impressed
2 the election results were announced and the m
2 parliament passed the new bill after a long d
2 the minister promised new policy on education
```

Documents about the same theme get the same topic number.

## Choosing the number of topics

- Try several values (5, 10, 20) and read the top words.
- Good topics are **distinct** and **make sense** to a human.
- Too few topics mix themes together; too many split one theme into near-duplicates.

## LDA in a sentence

LDA assumes each document is a **mix of topics** and each topic is a mix of words, and it works backwards to estimate both. It uses word **counts** (CountVectorizer) rather than TF-IDF.

## Uses

Organising support tickets, exploring survey answers, tagging articles, finding trends in reviews, and summarising a research collection.

:::note
Topic modeling needs a decent amount of text; with only a handful of documents the topics are unstable. Remove stop words and rare words first.
:::
