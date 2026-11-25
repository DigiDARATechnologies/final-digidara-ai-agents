---
title: Vector databases and indexing
summary: Understand how embeddings are stored and searched at scale: FAISS, Chroma, pgvector, approximate search and metadata filters.
takeaways:
- A vector database stores embeddings and finds the nearest ones quickly
- Exact search compares with everything; approximate search (HNSW) is much faster
- Metadata filters and good chunking matter as much as the database
---
## What problem it solves

In the embeddings lesson you compared a question with every stored vector. With a few thousand chunks that is fine; with millions it is too slow. A **vector database** (or vector index) finds the **nearest vectors** quickly and stores the text and metadata beside them.

## Exact vs approximate search

| | Exact (brute force) | Approximate (ANN) |
| --- | --- | --- |
| How | compare with every vector | smart index that checks a small part |
| Speed | slows as data grows | stays fast at millions |
| Accuracy | perfect | very high (say 95 to 99 percent recall) |

The popular approximate index is **HNSW**: a layered "small world" graph where search hops from a rough neighbour to closer and closer ones, like finding a street by first locating the city, then the district. Others: **IVF** (search only the nearest clusters) and **product quantization** (compress vectors).

## Options

| Tool | Notes |
| --- | --- |
| **FAISS** | a fast library from Meta (runs in your process) |
| **Chroma** | easy, open source, great for learning and small apps |
| **pgvector** | vectors inside **PostgreSQL**: one database for everything |
| **Qdrant, Weaviate, Milvus** | dedicated open-source servers |
| **Pinecone** | fully managed service |

If you already use PostgreSQL, **pgvector** is often the simplest choice.

## Chroma example

```python
import chromadb

client = chromadb.Client()
collection = client.create_collection("handbook")

collection.add(
    ids=["1", "2", "3"],
    documents=[
        "Students need 75 percent attendance to write the exams.",
        "The semester fee is due by the 10th of the month.",
        "The library is open from 8 am to 8 pm on weekdays.",
    ],
    metadatas=[{"topic": "attendance"}, {"topic": "fees"}, {"topic": "library"}],
)

result = collection.query(query_texts=["How much attendance is required?"], n_results=1)
print(result["documents"][0][0])
```

(Display only. Chroma embeds the text for you with a default model.)

## pgvector example

```sql
CREATE EXTENSION vector;
CREATE TABLE chunks (id serial PRIMARY KEY, body text, embedding vector(384));
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);

SELECT body FROM chunks ORDER BY embedding <=> '[0.12, -0.03, ...]' LIMIT 3;
```

`<=>` is the cosine distance operator; the query returns the three nearest chunks.

## Metadata filtering

Store facts beside each vector (document, year, department, language) and filter during search: "only the 2026 handbook, only the hostel section". This improves accuracy and keeps private data separate per user or college.

## Practical points

- Use the **same embedding model** for documents and queries, and keep its name in the metadata. Changing the model means re-embedding everything.
- Re-embed when documents change; delete old versions.
- The **chunking** strategy and embedding quality usually matter more than which database you pick.
- Check retrieval with a test set (hit rate) as in the advanced RAG lesson.

:::interview What is a vector database?
A database that stores embeddings with their text and metadata and finds the nearest vectors quickly using approximate indexes such as HNSW. It powers semantic search and RAG.
:::
