---
title: Building and deploying LLM apps
summary: Take an LLM idea to a working product: the app architecture, streaming, caching, cost and latency control, guardrails and monitoring.
takeaways:
- An LLM app is a normal app with a model call in the middle; the engineering around it decides quality
- Stream responses, cache repeats and pick the smallest model that passes your tests
- Add input and output guardrails, rate limits and monitoring before real users arrive
---
## The usual architecture

```text
User (web or mobile)
   -> your backend API   (auth, rate limits, logging)
        -> retrieve context (vector database, search, SQL)
        -> build the prompt
        -> call the LLM API
        -> check the output (guardrails, format)
   <- stream the answer back
```

Keep the **API key on the server** only, never in the browser. Keep prompts in files or config, not scattered in code, so you can version and test them.

## Stream the answer

An LLM produces one token at a time. If you wait for the whole answer, a 15 second reply feels frozen. **Streaming** sends tokens as they arrive so the user starts reading in about a second. Most APIs support it and web frameworks can forward it (server-sent events or WebSockets).

## Control cost and speed

| Technique | What it does |
| --- | --- |
| **Smaller model for easy tasks** | route simple requests to a cheap, fast model and hard ones to a strong model |
| **Shorter prompts** | send only the useful chunks and a short history |
| **Prompt caching** | many providers cheapen a repeated prompt prefix (system prompt, documents) |
| **Response caching** | store answers to identical or very similar questions |
| **Limit output** | set a maximum number of tokens |
| **Batching** | send many non-urgent jobs together at a lower price |

Always measure **cost per request** and **response time** from the start. A feature that costs more than it earns is a bug.

## Handle failures

Calls fail: rate limits, timeouts, provider outages. Plan for them.

```python
import time

def call_with_retry(call, tries=3):
    for attempt in range(tries):
        try:
            return call()
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt)   # wait 1s, 2s, 4s
```

Also set timeouts, have a fallback model or a friendly error message, and never let the whole page break because one call failed.

## Guardrails

- **Input**: limit length, strip secrets, detect prompt injection and abusive text.
- **Output**: validate JSON against a schema, filter private data, block unsafe content.
- **Scope**: the system prompt should say what the assistant will and will not do.
- **Rate limits** per user so one person cannot run up the bill.

## Monitor in production

Track: requests, errors, latency, tokens, cost, thumbs up and down, and the questions with no good answer. Review a sample of real conversations every week. Alert when cost or errors suddenly jump.

## Release safely

1. Test on your evaluation set.
2. Release to a small group first.
3. Watch the logs and feedback.
4. Roll out to everyone, and keep a quick way to switch back to the previous prompt or model.

:::tip For your project
A good student project: a document question-answering app with a simple web page, streaming answers, citations, a thumbs up or down button, and a README that shows your test results and cost per question.
:::
