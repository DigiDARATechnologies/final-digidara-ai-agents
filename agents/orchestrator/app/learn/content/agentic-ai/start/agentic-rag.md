---
title: Agentic RAG and knowledge agents
summary: Go beyond one-shot RAG: let an agent decide what to search, search several sources, check its findings and answer with evidence.
takeaways:
- Normal RAG searches once; agentic RAG decides when, where and how often to search
- The retriever becomes a tool the agent can call, rewrite and repeat
- Checking the evidence and admitting gaps matters more than answering quickly
---
## One-shot RAG has limits

Plain RAG: question, one search, one answer. It fails when:

- the question needs **several facts** from different places ("compare the fee and the scholarship rules")
- the first search returns **weak** results
- the answer needs **data and documents** together (a SQL table plus a policy PDF)

## Make search a tool

In agentic RAG the agent receives retrieval **as tools** and decides how to use them.

```python
tools = [
    {"name": "search_handbook", "description": "Search the college handbook text. Input: a short query."},
    {"name": "query_marks_db", "description": "Run a read-only SQL query on student marks."},
    {"name": "search_web", "description": "Search the public web for current information."},
]
```

The loop becomes:

```text
question -> think: what do I need?
   -> search_handbook("attendance rule")   -> read result
   -> not enough? search_handbook("medical certificate condonation") -> read result
   -> query_marks_db("select ...")        -> read result
   -> enough evidence? write the answer with sources
```

## What the agent does that plain RAG cannot

| Skill | Example |
| --- | --- |
| **Break the question down** | "compare A and B" becomes two searches |
| **Rewrite weak queries** | first search poor, try other words |
| **Choose the source** | policy question to documents, number question to SQL |
| **Verify** | cross-check two sources before trusting a fact |
| **Know when to stop** | enough evidence, or say "not found" |

## Keep it trustworthy

- **Cite every claim** with the source and passage.
- Set a **maximum number of searches** (for example 5) so it cannot loop and cost a fortune.
- Make the agent **say what it could not find** rather than filling the gap.
- Give database tools **read-only** access and validate queries.
- Treat retrieved text as **data, not instructions**; a document that says "ignore your rules" must be ignored (prompt injection).

## A simple pattern: plan, retrieve, check, answer

1. **Plan**: list the facts needed.
2. **Retrieve**: search for each fact.
3. **Check**: does the evidence cover every fact? If not, search again (within the limit).
4. **Answer**: write the final reply using only the evidence, with citations.

## When not to use it

If one search usually answers the question, plain RAG is faster and cheaper. Use the agentic version for **multi-part, multi-source or research-style questions**, and measure that it really improves your test set.

:::remember
Agentic RAG = RAG where the model chooses the searches. More power, more cost, so add limits and checks.
:::
