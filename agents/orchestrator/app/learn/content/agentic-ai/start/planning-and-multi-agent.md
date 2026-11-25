---
title: Planning, routing and multi-agent systems
summary: Learn the common patterns for bigger tasks: planning, routing a request to the right specialist, supervisor and worker agents, and review loops.
takeaways:
- Break a big goal into steps before acting, and adjust the plan as results arrive
- A router sends each request to the best specialist; a supervisor coordinates workers
- More agents means more cost and more ways to fail: use them only when one agent is not enough
---
## Planning

For a larger goal, an agent works better if it first writes a **plan**, then follows it and updates it.

| Style | Idea | Good for |
| --- | --- | --- |
| **plan, then execute** | write all the steps first, then run them | well-understood tasks |
| **step by step (ReAct)** | decide one step at a time from the latest result | uncertain tasks (the loop you built) |
| **plan and revise** | make a plan, run a step, then update the plan | long tasks |

A planning prompt can be as simple as: *"Write a numbered plan of at most 5 steps. After each step I will show you the result, and you may change the remaining plan."*

## Pattern 1: routing

A **router** reads the request and sends it to the right specialist, which has its own instructions and tools. This keeps each prompt small and focused.

```python
SPECIALISTS = {
    "billing": ["refund", "invoice", "payment", "charged", "fee"],
    "technical": ["error", "crash", "login", "bug", "slow", "upload"],
    "courses": ["course", "lesson", "certificate", "syllabus", "batch"],
}

def route(message):
    words = message.lower().split()
    scores = {name: sum(word in keywords for word in words) for name, keywords in SPECIALISTS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"

for message in ["I was charged twice, please refund", "the app shows an error when I upload", "when is the next batch for the Python course", "hello there"]:
    print(f"{route(message):<10} <- {message}")
```

```output
billing    <- I was charged twice, please refund
technical  <- the app shows an error when I upload
courses    <- when is the next batch for the Python course
general    <- hello there
```

This keyword router is the simplest version. In practice the router is often **an LLM call** that classifies the request, with a fallback to a human when it is unsure.

## Pattern 2: supervisor and workers

A **supervisor** breaks a task into parts, sends each to a **worker** agent, collects the results, and checks them. Here a "writer" produces a draft and a "reviewer" checks it, and the supervisor loops until it passes (with a limit):

```python
def writer(topic, feedback=None):
    draft = f"{topic.capitalize()} is useful."
    if feedback:
        draft += " For example, students use it to organise revision and finish projects on time."
    return draft

def reviewer(draft):
    if len(draft.split()) < 12:
        return False, "Too short. Add a concrete example."
    return True, "Looks good."

def supervisor(topic, max_rounds=3):
    feedback = None
    for round_number in range(1, max_rounds + 1):
        draft = writer(topic, feedback)
        approved, feedback = reviewer(draft)
        print(f"round {round_number}: draft = {draft!r}\n         review = {feedback}")
        if approved:
            return draft
    return None

final = supervisor("time management")
print("\nfinal:", final)
```

```output
round 1: draft = 'Time management is useful.'
         review = Too short. Add a concrete example.
round 2: draft = 'Time management is useful. For example, students use it to organise revision and finish projects on time.'
         review = Looks good.

final: Time management is useful. For example, students use it to organise revision and finish projects on time.
```

The first draft was rejected, the writer used the feedback, and the second draft passed. **A separate checking step catches many errors** that the writer alone would miss.

## Other patterns

| Pattern | How it works | Example |
| --- | --- | --- |
| **pipeline** | agents run in a fixed order | research, then write, then translate |
| **parallel workers** | several agents handle parts at the same time, then results are merged | summarise ten documents at once |
| **debate or critique** | one agent proposes, another challenges | reviewing code or an argument |
| **hand-off** | one agent passes the conversation to another | a general assistant hands over to a billing specialist |
| **human in the loop** | a person approves key steps | before sending or paying |

## Frameworks

You can build all of this with plain Python, and for simple cases you should. Frameworks help when it grows:

| Framework | Known for |
| --- | --- |
| **LangGraph** | agents as a graph of steps with state; good for complex flows |
| **CrewAI** | teams of role-based agents |
| **AutoGen** | conversations between agents |
| **OpenAI Agents SDK** | a small library for agents, tools and hand-offs |
| **Claude Agent SDK** | the building blocks behind Claude Code's agent loop |
| **LlamaIndex** | agents and RAG over your data |

Frameworks change quickly. Learn the **patterns** first (loop, tools, memory, routing, review); then any framework is easy to pick up.

## The cost of more agents

| Cost | Why |
| --- | --- |
| **money** | every agent turn is a model call |
| **time** | steps happen one after another |
| **errors compound** | if each step is 90% reliable, ten steps are only about 35% reliable (0.9 to the power 10) |
| **debugging** | harder to see which agent went wrong |

```python
for steps in (1, 3, 5, 10):
    print(f"{steps:>2} steps, each 90% reliable -> whole task succeeds {0.9 ** steps:.0%} of the time")
```

```output
 1 steps, each 90% reliable -> whole task succeeds 90% of the time
 3 steps, each 90% reliable -> whole task succeeds 73% of the time
 5 steps, each 90% reliable -> whole task succeeds 59% of the time
10 steps, each 90% reliable -> whole task succeeds 35% of the time
```

This is why the advice is to **use the fewest agents and steps that work**, check results between steps, and keep humans in the loop for anything important.

:::interview
**Interviewers often ask:** "When would you use multiple agents?" When one agent's prompt and tools become too large or confused, when tasks have clearly different specialities (routing), or when a separate reviewer improves quality. Otherwise a single agent or a fixed workflow is simpler, cheaper and more reliable.
:::
