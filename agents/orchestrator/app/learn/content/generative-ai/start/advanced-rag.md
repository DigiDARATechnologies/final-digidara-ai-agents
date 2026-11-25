---
title: Advanced RAG: making retrieval accurate
summary: Fix the common reasons RAG gives poor answers: better chunking, hybrid search, reranking, query rewriting, and checking the result.
takeaways:
- Most bad RAG answers come from bad retrieval, not a bad model
- Hybrid search (keywords plus embeddings) and reranking find the right passages more reliably
- Measure retrieval separately from generation so you know what to fix
---
## Find the real problem first

When a RAG answer is wrong, ask which step failed:

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| The answer is missing a fact that is in the documents | the right chunk was **not retrieved** | better chunking, hybrid search, more results, query rewriting |
| The right chunk was retrieved but the answer ignores it | the **prompt or model** | clearer instructions, fewer but better chunks, reranking |
| The answer is confident but invented | no "I do not know" rule | grounded prompt with citations |

Always check **retrieval first**: print the chunks that were sent to the model.

## 1. Better chunking

- Split on **meaning** (headings, paragraphs), not blindly every N characters.
- Keep chunks about 200 to 500 words, with a small overlap.
- Store **metadata** with each chunk: document name, page, date, section. It allows filtering ("only the 2026 handbook") and citations.
- For tables and code, keep each table or function together.

## 2. Hybrid search

Embeddings find **meaning** ("fees" matches "tuition payment") but can miss exact terms such as a course code `CS-204` or an error number. Keyword search (BM25) finds exact words but misses synonyms. **Hybrid search runs both and merges the results.**

```python
def hybrid(question, keyword_search, vector_search, k=5):
    scores = {}
    for rank, chunk_id in enumerate(keyword_search(question)):
        scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (60 + rank)
    for rank, chunk_id in enumerate(vector_search(question)):
        scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (60 + rank)
    return sorted(scores, key=scores.get, reverse=True)[:k]
```

A chunk ranked high by **both** lists wins. This simple merge is called reciprocal rank fusion.

## 3. Rerank

Retrieve a wide set (say 20 chunks) quickly, then use a more careful model, a **reranker**, to read the question with each chunk and score how well it answers. Keep the best 3 to 5. It is slower than vector search but more accurate, so it is used only on the short list.

## 4. Rewrite the question

Users write "and the fee for that?" which means nothing alone. Before searching, ask the model to **rewrite** it using the chat history: "What is the late fee for semester fees?" Other tricks:

- **Multi-query**: generate 3 versions of the question and search all.
- **HyDE**: let the model write a short imaginary answer and search with that, since an answer looks more like the documents than a question does.

## 5. Check the answer

- Ask for **citations** and verify each one exists in the retrieved text.
- If the best retrieval score is below a threshold, answer "I could not find this in the documents" instead of guessing.

## Measure retrieval

Make a small test set of 30 to 50 real questions, each with the document that holds the answer. Then measure:

| Metric | Meaning |
| --- | --- |
| **Hit rate @k** | for what share of questions was the right chunk in the top k? |
| **MRR** | how high was the right chunk ranked, on average? |

Change one thing at a time (chunk size, hybrid, reranker) and keep what raises the numbers.

:::interview What is hybrid search and why use it?
Hybrid search combines keyword search (exact terms) with embedding search (meaning) and merges the rankings. It handles both codes and names, and paraphrased questions, so it retrieves more reliably than either alone.
:::
