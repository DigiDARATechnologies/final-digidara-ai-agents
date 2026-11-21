---
title: Memory and context management
summary: Learn how an agent remembers: the conversation window, trimming and summarising, and long-term memory for facts that must last.
takeaways:
- A model has no memory of its own; everything it "remembers" must be sent in the prompt
- Short-term memory is the recent conversation; long-term memory is stored outside and retrieved when needed
- Trim or summarise old messages so the context window never overflows
---
## Memory is something you build

The model forgets everything between calls. An agent's "memory" is just **what your code puts back into the prompt**.

| Kind | What it holds | How it works |
| --- | --- | --- |
| **short-term** | the current conversation and tool results | the message list you send each turn |
| **long-term** | facts that should last (preferences, past decisions, notes) | saved in a file or database, retrieved when relevant |
| **working notes** | the plan and progress of a long task | a scratchpad the agent updates |

## The problem: history grows

Every turn adds messages, and the **whole history is sent every time**. It becomes slow, costly, and eventually larger than the context window.

## Strategy 1: a sliding window

Keep the system instructions and only the **most recent** messages that fit a token budget:

```python
def rough_tokens(text):
    return max(1, round(len(text) / 4))

def trim_history(messages, budget):
    kept, used = [], 0
    for message in reversed(messages):                       # start from the newest
        cost = rough_tokens(message["content"])
        if used + cost > budget:
            break
        kept.append(message)
        used += cost
    return list(reversed(kept)), used

conversation = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"message number {i} " + "x" * 60} for i in range(1, 13)]

trimmed, used = trim_history(conversation, budget=60)
print("messages before:", len(conversation), "| after trimming:", len(trimmed), "| tokens used:", used)
print("kept messages:", [m["content"].split()[2] for m in trimmed])
```

```output
messages before: 12 | after trimming: 3 | tokens used: 60
kept messages: ['10', '11', '12']
```

Only the latest messages survive. The risk: **early but important facts are lost** (the user's name, their goal).

## Strategy 2: summarise the old part

Instead of dropping old messages, replace them with a **short summary**, written by the model itself:

```py
summary = client.messages.create(
    model="claude-sonnet-5-5", max_tokens=200,
    messages=[{"role": "user", "content": "Summarise this conversation in 5 bullet points, keeping names, goals and decisions:\n\n" + old_text}],
).content[0].text

history = [{"role": "user", "content": "Summary of the conversation so far:\n" + summary}] + recent_messages
```

A good rule: keep the **last few turns word for word**, and a **summary** of everything before them.

## Strategy 3: long-term memory

For facts that must survive between sessions, **store them outside the model** and bring back only what is relevant:

```python
memory = []                                                   # in a real system: a database or a vector store

def remember(fact):
    memory.append(fact)

def recall(question, top_k=2):
    question_words = set(question.lower().split())
    scored = [(len(question_words & set(fact.lower().split())), fact) for fact in memory]
    return [fact for score, fact in sorted(scored, reverse=True)[:top_k] if score > 0]

remember("The student's name is Priya and she is in second year computer science.")
remember("Priya's weak topics are recursion and SQL joins.")
remember("Priya prefers short explanations with examples.")
remember("The placement test is on 12 December.")

print(recall("what are her weak topics in SQL"))
print(recall("when is the placement test"))
```

```output
["Priya's weak topics are recursion and SQL joins.", "The student's name is Priya and she is in second year computer science."]
['The placement test is on 12 December.', "The student's name is Priya and she is in second year computer science."]
```

Each recalled fact goes into the prompt only when it helps. Notice that the first question also pulled in a second, weaker fact (the student's name), which matched only the little word "in". Matching shared words is crude. Real systems use **embeddings and a vector database** for this step (the embeddings lesson), so a question like "what does she struggle with?" would still find the "weak topics" fact even without shared words, and would rank weak matches lower.

## What to store, and what not to

| Store | Do not store |
| --- | --- |
| stable preferences and goals | passwords, keys, payment details |
| decisions and their reasons | sensitive personal data unless truly needed and allowed |
| the outcome of finished tasks | every message (it becomes noise) |
| notes the user asked you to remember | guesses that were never confirmed |

:::warning
Long-term memory is personal data. Tell users what is remembered, let them see and delete it, and keep each user's memory separate. A memory leak between users is a serious privacy failure.
:::

## Good practice

| Habit | Why |
| --- | --- |
| budget tokens: instructions, memory, documents, history, and room for the answer | nothing overflows |
| put important facts **near the end** of long prompts, or repeat them | models can lose details in the middle |
| let the agent write a short **progress note** during long tasks | it can continue after a trim |
| test long conversations | many failures only appear after 30 turns |
