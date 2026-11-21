---
title: Using LLM APIs in your code
summary: Call a language model from Python, understand messages, system prompts and streaming, and handle keys, errors, retries and costs safely.
takeaways:
- An LLM API takes a list of messages and returns the model's reply
- Keep API keys in environment variables, never in code or GitHub
- Plan for failures: timeouts, rate limits and invalid answers
---
## The basic call

Every provider (Anthropic, OpenAI, Google and others) works the same way: you send **messages** and receive a reply. Here is the shape of a call with the Anthropic Python library (install it with `pip install anthropic`, and set the `ANTHROPIC_API_KEY` environment variable):

```py
import anthropic

client = anthropic.Anthropic()            # reads the key from the ANTHROPIC_API_KEY environment variable

message = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=300,
    system="You are a friendly Python tutor. Answer in at most 4 sentences.",
    messages=[{"role": "user", "content": "What is a list comprehension?"}],
)
print(message.content[0].text)
print("tokens used:", message.usage.input_tokens, "in,", message.usage.output_tokens, "out")
```

Check the provider's documentation for the current model names, because they change often. Other providers use a very similar pattern.

| Part | Meaning |
| --- | --- |
| `model` | which model to use (bigger is smarter and costlier) |
| `system` | standing instructions for the whole conversation |
| `messages` | the conversation: alternating `user` and `assistant` turns |
| `max_tokens` | the longest reply allowed |
| `usage` | tokens used, so you can track cost |

## A conversation is a list

The model has **no memory** between calls. To continue a conversation you send the **whole history** every time:

```python
history = [
    {"role": "user", "content": "What is a list comprehension?"},
    {"role": "assistant", "content": "It is a short way to build a list from another list."},
    {"role": "user", "content": "Show me one with a condition."},          # this only makes sense with the history above
]

def count_turns(messages):
    return sum(1 for m in messages if m["role"] == "user")

print("turns in the conversation:", count_turns(history))
print("the model sees all", len(history), "messages every time you call it")
```

```output
turns in the conversation: 2
the model sees all 3 messages every time you call it
```

That is why long chats cost more and slow down: the whole history is sent as input each turn. Trim or summarise old turns (the agent memory lesson shows how).

## Streaming

For a chat interface, show words as they arrive instead of waiting for the full reply:

```py
with client.messages.stream(model="claude-sonnet-5-5", max_tokens=300,
                            messages=[{"role": "user", "content": "Explain recursion simply."}]) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
```

## Keep keys safe

```python
import os

def get_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("Set the ANTHROPIC_API_KEY environment variable first (never write the key in the code).")
    return key

try:
    get_key()
except RuntimeError as error:
    print("Stopped safely:", error)
```

```output
Stopped safely: Set the ANTHROPIC_API_KEY environment variable first (never write the key in the code).
```

| Do | Do not |
| --- | --- |
| put the key in an environment variable or a `.env` file listed in `.gitignore` | paste it into your code |
| keep calls on your **server** | call the API from browser JavaScript, where anyone can read your key |
| set a spending limit in the provider dashboard | leave a key without limits |
| rotate the key at once if it leaks | assume deleting a commit hides it |

## Handle failures

Network calls fail: timeouts, rate limits (too many requests), overloaded servers. Retry with **exponential backoff** (wait 1 second, then 2, then 4...):

```python
import random
import time

attempts = {"count": 0}

def flaky_call():
    attempts["count"] += 1
    if attempts["count"] < 3:
        raise ConnectionError("temporary failure")          # fails twice, then works
    return "the answer"

def with_retries(function, max_tries=5, base_delay=0.01):
    for attempt in range(1, max_tries + 1):
        try:
            return function()
        except ConnectionError as error:
            if attempt == max_tries:
                raise
            delay = base_delay * 2 ** (attempt - 1) + random.uniform(0, base_delay)       # backoff with a little randomness
            print(f"attempt {attempt} failed ({error}); waiting {delay:.3f} s")
            time.sleep(delay)

print("result:", with_retries(flaky_call))
```

```output
attempt 1 failed (temporary failure); waiting 0.011 s
attempt 2 failed (temporary failure); waiting 0.023 s
result: the answer
```

Most official libraries already retry some errors for you. Always set a **timeout**, and decide what your app does when the call finally fails (show a friendly message, fall back, or queue it).

## Good habits for LLM apps

| Habit | Why |
| --- | --- |
| validate every structured answer | the model can break the format |
| log prompts, replies, tokens and time (without private data) | debugging and cost control |
| set `max_tokens` and a budget per user | stop surprise bills |
| keep the prompt and the model name in config | change them without new code |
| never put untrusted text in the system prompt | the safety lesson explains why |
| test with a fixed set of questions | notice when a change makes answers worse |

:::interview
**Interviewers often ask:** "How do you keep a conversation going with an LLM API?" The API is stateless, so you send the full message history each time (or a trimmed or summarised version) and append the new reply to it.
:::
