---
title: Evaluating LLM applications
summary: Learn how to test something that gives a different answer every time: build a test set, score with rules and an LLM judge, and catch regressions before users do.
takeaways:
- You cannot trust an LLM app by trying three prompts; build a test set of real cases
- Use simple checks where possible and an LLM judge for open-ended answers
- Re-run the test set after every change to prompt, model or documents
---
## Why testing is different

Normal code returns the same output for the same input, so a test says `assert result == 5`. An LLM can word the same correct answer in many ways, and a small prompt change can break something elsewhere. We need **evaluation**: a repeatable way to measure quality.

## Step 1: build a test set

Collect 30 to 100 realistic cases. For each one write:

- the **input** (question or task)
- what a **good answer** must contain (key facts, or a reference answer)
- optional: what it must **not** do

Include normal cases, tricky cases, questions with no answer in the documents, and unsafe requests. Real user questions beat invented ones.

## Step 2: score the answers

| Method | Use it for | Example |
| --- | --- | --- |
| **Exact or rule check** | structured output | valid JSON, has all fields, number equals 75 |
| **Contains / regex** | must mention a fact | answer includes "75 percent" |
| **Similarity** | close to a reference | embedding similarity above 0.85 |
| **LLM as judge** | open-ended quality | a second model grades helpfulness and accuracy |
| **Human review** | final truth, small samples | trainers rate 20 answers |

Prefer the simplest method that works.

## LLM as judge

Ask a strong model to grade an answer against a rubric. Give it a clear scale and ask for a short reason.

```python
JUDGE_PROMPT = """You are grading an answer.
Question: {question}
Reference facts: {facts}
Answer: {answer}

Score 1 to 5 for factual correctness against the reference facts only.
Reply as JSON: {{"score": <1-5>, "reason": "<one sentence>"}}"""
```

Cautions: judges favour long answers, can favour their own style, and sometimes make mistakes. Use a clear rubric, check a sample by hand, and compare scores across versions rather than trusting one number.

## Step 3: measure RAG and agents in parts

- **Retrieval**: did the right passage come back? (hit rate)
- **Faithfulness**: is every claim in the answer supported by the passages?
- **Answer relevance**: does it actually answer the question?
- **Safety**: does it refuse what it should?

For agents also check the **steps**: right tool, right arguments, no loops.

## Step 4: run it on every change

```text
change prompt / model / documents
      -> run the test set
      -> compare scores with the last version
      -> ship only if nothing important got worse
```

Keep a table of version, date, pass rate and cost per question. This is called a **regression test**, and it is what turns a demo into a product.

## After launch

- Log questions, answers and the retrieved text (without private data).
- Add a thumbs up or down button and review the thumbs down.
- Turn every real failure into a new test case.

:::remember
No test set, no confidence. Ten good test cases beat a hundred hand-picked demos.
:::
