---
title: Optimising agent cost and latency
summary: Make agents faster and cheaper: fewer steps, smaller models, caching, parallel tool calls and tight context.
takeaways:
- Cost and delay grow with every step and every token in the context
- Use small models for easy steps, caching, and parallel calls
- Measure cost and time per task before and after each change
---
## Why agents get expensive

An agent loop calls the model many times, and **each call re-sends the whole conversation**. A task with 10 steps and a 5,000-token context reads about 50,000 tokens. Cost and delay climb quickly, so design for efficiency.

## Measure first

Log for each task: number of steps, input and output tokens, tool time, total seconds and cost. Optimise the **biggest** item, and re-measure after each change.

## Ways to cut cost and time

| Technique | Effect |
| --- | --- |
| **Fewer steps** | better tools and prompts so the agent needs fewer rounds |
| **Smaller model for easy steps** | routing, classification and formatting rarely need the biggest model |
| **Shorter context** | summarise old messages, drop irrelevant tool output |
| **Compact tool results** | return only the needed fields |
| **Prompt caching** | the repeated beginning (system prompt, tool list, documents) is billed cheaper by many providers; keep it **stable and first** |
| **Response caching** | store results of identical tool calls and questions |
| **Parallel tool calls** | independent calls (search three sites) run together |
| **Streaming** | show progress so waiting feels shorter |
| **Stop early** | stop as soon as the goal is met; set a step limit |
| **Batching** | run non-urgent jobs together at lower prices |

## Parallel calls

```python
import asyncio

async def research(topics):
    results = await asyncio.gather(*(search_tool(topic) for topic in topics))
    return dict(zip(topics, results))

# three searches take the time of one instead of three
```

## Model routing

```python
def pick_model(task_type):
    if task_type in ("classify", "extract", "format"):
        return "small-fast-model"
    if task_type in ("plan", "hard-reasoning", "code"):
        return "large-model"
    return "medium-model"
```

Test that the small model passes your evaluation set for those steps before switching.

## Keep context small

- Summarise finished sub-tasks into a short note.
- Store large documents outside the prompt and fetch only the relevant chunks.
- Remove tool results once they are no longer needed.

## Budgets in code

```python
class Budget:
    def __init__(self, max_steps=12, max_cost=0.50):
        self.steps, self.cost = 0, 0.0
        self.max_steps, self.max_cost = max_steps, max_cost

    def charge(self, cost):
        self.steps += 1
        self.cost += cost
        if self.steps > self.max_steps or self.cost > self.max_cost:
            raise RuntimeError("Budget exceeded, stopping the agent")
```

## The quality trade-off

Cheaper must not mean worse. After each change, **re-run your evaluation set**. Keep the change only if quality stays acceptable and cost or latency improves.

:::remember
The cheapest step is the one you do not need. Reduce steps first, then shrink the model and the context.
:::
