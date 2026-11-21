---
title: RAG: answering from your own documents
summary: Build a retrieval-augmented generation pipeline: split documents into chunks, retrieve the best ones, and give them to the model so its answer is grounded and cited.
takeaways:
- RAG retrieves relevant passages first, then asks the model to answer using only them
- Chunking and retrieval quality decide the quality of the answer
- A grounded prompt, with sources and an "I do not know" rule, reduces hallucination
---
## Why RAG

An LLM does not know your college handbook, your product manuals or yesterday's news, and it may invent an answer. **Retrieval-augmented generation (RAG)** fixes this:

1. **Retrieve**: find the passages from your documents that are relevant to the question.
2. **Augment**: put those passages in the prompt.
3. **Generate**: ask the model to answer **using only that text**, and to cite it.

| Compared with | RAG advantage |
| --- | --- |
| a plain LLM | answers from **your** and **current** data, with sources |
| fine-tuning | no retraining; update by changing documents; cheaper |
| pasting everything into the prompt | only the relevant parts are sent, which cuts cost and confusion |

## Step 1: chunk the documents

Long documents must be split into **chunks** (a few sentences to a few paragraphs) so retrieval can return precise passages. Overlap neighbours slightly so an idea is not cut in half.

```python
def chunk_text(text, max_words=40, overlap=10):
    words = text.split()
    chunks, start = [], 0
    while start < len(words):
        chunks.append(" ".join(words[start:start + max_words]))
        if start + max_words >= len(words):
            break
        start += max_words - overlap
    return chunks

handbook = (
    "Attendance: students must keep at least 75 percent attendance to write the semester exams. "
    "Students below 75 percent need a medical certificate and the principal's permission. "
    "Fees: the semester fee is due by the 10th of the month the semester begins. A late fee of 500 rupees applies after that date. "
    "Scholarships: students with a CGPA above 8.5 can apply for the merit scholarship before 30 June. "
    "Library: the library is open from 8 am to 8 pm on weekdays and books can be borrowed for 14 days. "
    "Hostel: hostel rooms are allotted on a first come first served basis after the admission is confirmed."
)

chunks = chunk_text(handbook, max_words=22, overlap=5)
print(len(chunks), "chunks")
for number, chunk in enumerate(chunks, start=1):
    print(f"{number}. {chunk}")
```

```output
6 chunks
1. Attendance: students must keep at least 75 percent attendance to write the semester exams. Students below 75 percent need a medical certificate
2. percent need a medical certificate and the principal's permission. Fees: the semester fee is due by the 10th of the month the
3. 10th of the month the semester begins. A late fee of 500 rupees applies after that date. Scholarships: students with a CGPA
4. Scholarships: students with a CGPA above 8.5 can apply for the merit scholarship before 30 June. Library: the library is open from
5. the library is open from 8 am to 8 pm on weekdays and books can be borrowed for 14 days. Hostel: hostel
6. for 14 days. Hostel: hostel rooms are allotted on a first come first served basis after the admission is confirmed.
```

Chunk size is a trade-off: too small and a chunk lacks context; too large and it mixes topics and wastes the model's attention. Good starting points are 200 to 500 tokens with 10 to 20% overlap, tested on real questions.

## Step 2: retrieve the best chunks

To keep the example runnable offline we score chunks with **TF-IDF** (from the NLP course). In a real RAG system you would use an **embedding model and a vector database** (the previous lesson); the pipeline around it stays the same.

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

vectorizer = TfidfVectorizer(stop_words="english")
chunk_vectors = vectorizer.fit_transform(chunks)

def retrieve(question, top_k=2, min_score=0.1):
    scores = cosine_similarity(vectorizer.transform([question]), chunk_vectors)[0]
    best = scores.argsort()[::-1][:top_k]
    return [(int(i), float(scores[i])) for i in best if scores[i] >= min_score]

for question in ["What attendance do I need to write the exams?", "When is the semester fee due and what is the late fee?", "Who won the cricket match?"]:
    hits = retrieve(question)
    print(f"Q: {question}")
    print("   retrieved chunks:", [(n + 1, round(s, 2)) for n, s in hits] or "nothing relevant")
```

```output
Q: What attendance do I need to write the exams?
   retrieved chunks: [(1, 0.59), (2, 0.12)]
Q: When is the semester fee due and what is the late fee?
   retrieved chunks: [(3, 0.43), (2, 0.31)]
Q: Who won the cricket match?
   retrieved chunks: nothing relevant
```

The first two questions find the right chunks. The cricket question finds **nothing relevant**, so the system must **not** let the model guess.

## Step 3: build the grounded prompt

```python
def build_rag_prompt(question):
    hits = retrieve(question)
    if not hits:
        return None
    context = "\n".join(f"[{n + 1}] {chunks[n]}" for n, _ in hits)
    return (
        "Answer the question using ONLY the sources below. "
        "Cite the source numbers like [1]. "
        "If the sources do not contain the answer, say: I could not find this in the documents.\n\n"
        f"Sources:\n{context}\n\nQuestion: {question}\nAnswer:"
    )

prompt = build_rag_prompt("What attendance do I need to write the exams?")
print(prompt)
print()
print("prompt for an off-topic question:", build_rag_prompt("Who won the cricket match?"))
```

```output
Answer the question using ONLY the sources below. Cite the source numbers like [1]. If the sources do not contain the answer, say: I could not find this in the documents.

Sources:
[1] Attendance: students must keep at least 75 percent attendance to write the semester exams. Students below 75 percent need a medical certificate
[2] percent need a medical certificate and the principal's permission. Fees: the semester fee is due by the 10th of the month the

Question: What attendance do I need to write the exams?
Answer:

prompt for an off-topic question: None
```

Three things make this prompt safe and useful: the model is told to use **only** the sources, it must **cite** them, and it has a clear way to say it does not know. When nothing is retrieved, we skip the model call completely.

## Step 4: send it to the model

```py
import anthropic

client = anthropic.Anthropic()
prompt = build_rag_prompt("What attendance do I need to write the exams?")
if prompt is None:
    answer = "I could not find this in the documents."
else:
    reply = client.messages.create(model="claude-sonnet-5-5", max_tokens=300, messages=[{"role": "user", "content": prompt}])
    answer = reply.content[0].text
print(answer)
```

A good answer would read: "You need at least 75 percent attendance [1]. Below that you need a medical certificate [1] and the principal's permission [2]." The numbers in brackets let the student check the source.

Notice how chunk 1 stops just before "and the principal's permission", which sits at the start of chunk 2. This is a **chunk boundary** problem, and it is exactly why we retrieve **more than one** chunk and why the overlap between chunks matters. If we had retrieved only the top chunk, the answer would have been incomplete.

## Where RAG goes wrong

| Problem | Cause | Fix |
| --- | --- | --- |
| a wrong or missing answer | the right chunk was not retrieved | better chunking, embeddings, more results, a reranker |
| an answer that mixes sources | chunks too large or unrelated | smaller chunks, cleaner documents |
| made-up details | the model ignored "only the sources" | stricter prompt, lower temperature, check citations |
| outdated answers | stale documents | re-index when documents change |
| it answers things it should refuse | no relevance threshold | the `min_score` check, and an "I do not know" rule |
| private documents shown to the wrong person | no access control | filter retrieval by who is asking |

## Improving RAG (in the order to try)

| Step | Idea |
| --- | --- |
| 1 | clean the source documents (remove headers, fix tables) |
| 2 | tune the chunk size and overlap on real questions |
| 3 | use a good embedding model, and combine keyword and vector search (**hybrid search**) |
| 4 | add a **reranker** that reorders the top results by relevance |
| 5 | add metadata (course, date, language) and filter by it |
| 6 | measure with a test set of questions and expected sources |

:::warning
RAG reduces made-up answers but does not remove them. Always show the sources, and **test with questions whose answers are not in your documents**, to check that the system says "I do not know".
:::

:::practice capstone-project
RAG over your own notes or college documents is a strong portfolio project. Share your plan with the Capstone Project agent and ask which questions you should use as a test set.
:::
