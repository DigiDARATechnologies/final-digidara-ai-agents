---
title: Embeddings and semantic search
summary: Turn text into vectors that capture meaning, search by meaning instead of keywords, and see how a vector database works.
takeaways:
- An embedding is a list of numbers that represents the meaning of a piece of text
- Similar meanings give vectors that point the same way, measured by cosine similarity
- Semantic search finds the closest vectors to the question, which is the base of RAG
---
## Search by meaning

Keyword search misses "how do I get my money back" when the page says "refund policy". An **embedding model** turns each piece of text into a **vector** (hundreds or thousands of numbers) so that texts with **similar meaning** get **similar vectors**, even with no shared words.

```py
# how it looks with a real embedding model (sentence-transformers)
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("all-MiniLM-L6-v2")
vectors = model.encode(["How do I get my money back?", "Refund policy", "Bus timings"])
```

Real providers also offer embedding APIs. The idea below is the same whichever you use.

## The mechanics: vectors and cosine similarity

To keep this runnable anywhere, we use small made-up vectors for four documents. Real embeddings have hundreds of numbers, but the search steps are identical.

```python
import numpy as np

documents = ["Refund policy: money is returned within 7 days", "How to reset your password", "Course fees and payment plans", "Bus timings for the college campus"]
vectors = np.array([
    [0.9, 0.1, 0.4, 0.0],      # refund
    [0.1, 0.9, 0.0, 0.1],      # password
    [0.7, 0.0, 0.7, 0.1],      # fees and payment
    [0.0, 0.1, 0.0, 0.9],      # buses
])

def cosine_scores(query_vector, matrix):
    query_vector = query_vector / np.linalg.norm(query_vector)
    matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix @ query_vector

question_vector = np.array([0.8, 0.05, 0.5, 0.0])                 # "how do I get my money back?" (made-up numbers)
scores = cosine_scores(question_vector, vectors)

for index in np.argsort(scores)[::-1]:
    print(f"{scores[index]:.2f}  {documents[index]}")
```

```output
0.99  Refund policy: money is returned within 7 days
0.97  Course fees and payment plans
0.15  How to reset your password
0.01  Bus timings for the college campus
```

The refund document and the fees document, the closest in meaning, score highest, and buses scores lowest. A **vector search** is exactly this: embed the question, score every stored vector, and return the top matches.

## At scale: vector databases

Comparing a question with millions of vectors one by one is slow. **Vector databases** store vectors and use clever indexes to find close ones fast.

| Tool | Notes |
| --- | --- |
| **FAISS** | a fast library from Meta, runs in your own program |
| **Chroma** | simple, popular for learning and small apps |
| **pgvector** | vector search inside PostgreSQL, handy if you already use it |
| **Pinecone, Weaviate, Qdrant** | hosted or self-hosted databases built for vectors |

```py
# a small example with Chroma (pip install chromadb)
import chromadb

client = chromadb.Client()
collection = client.create_collection("faq")
collection.add(ids=["1", "2", "3"], documents=["Refund policy ...", "How to reset your password ...", "Bus timings ..."])

result = collection.query(query_texts=["how do I get my money back?"], n_results=2)
print(result["documents"])
```

Chroma embeds the text for you here with a default model. In a real project you choose the embedding model yourself.

## Choosing and using embeddings

| Point | Advice |
| --- | --- |
| **use the same model** for documents and questions | vectors from different models cannot be compared |
| **chunk long documents** | one vector per page blurs many topics; use short passages |
| **multilingual** content | pick a multilingual embedding model; test with real Tamil, Hindi and mixed text |
| **cosine similarity** | the usual way to compare; scores near 1 are very similar |
| **keep the original text** next to each vector | you need it to show sources and feed the LLM |
| **re-embed** if you change the model | old vectors become useless |

## Beyond question answering

| Use | How embeddings help |
| --- | --- |
| **semantic search** | find documents by meaning |
| **recommendations** | items close to what a user liked |
| **duplicate detection** | find near-identical questions or tickets |
| **clustering and topic discovery** | group similar texts |
| **classification** with little data | train a simple classifier on the vectors |

:::warning
Similar vectors are **similar**, not necessarily **correct**. Search can return a related but wrong passage, so show sources, and let the model say "I could not find this in the documents".
:::
