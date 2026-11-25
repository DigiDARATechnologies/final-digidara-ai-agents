---
title: Multi-agent systems
summary: Understand when several cooperating agents help, and the supervisor, handoff, pipeline and debate patterns.
takeaways:
- Split work among agents only when roles or tools are truly different
- Common shapes: supervisor, pipeline, handoff and reviewer
- More agents add cost and failure points, so start with one
---
## Why use several agents

One agent with 30 tools and a huge prompt gets confused. Splitting into **specialists** can help because each has:

- a **focused prompt** and a **small toolset**
- its **own context**, so it is not cluttered
- a clear **responsibility** that is easier to test

But every extra agent adds cost, delay and a way to fail. **Start with one agent**; split only when you see a clear reason.

## Pattern 1: supervisor (manager and workers)

A **supervisor** agent breaks the goal into tasks, sends each to a **worker**, and combines the results.

```text
User: "Prepare a market brief on e-scooters"
Supervisor -> Researcher (searches the web)
           -> Analyst   (reads numbers, makes a table)
           -> Writer    (writes the brief)
Supervisor -> checks and returns the final brief
```

## Pattern 2: pipeline

A fixed chain: each agent's output is the next one's input.

`Extractor -> Validator -> Summariser -> Formatter`

Predictable and easy to debug. Often a plain workflow is enough.

## Pattern 3: handoff

An agent **passes the conversation** to a better-suited one. A general support agent hands a billing question to the billing agent, which has payment tools.

## Pattern 4: reviewer (maker and checker)

One agent produces, another **critiques** with different instructions (security reviewer, fact checker). Use objective checks when possible.

## Pattern 5: debate or voting

Several agents answer independently and a judge picks or merges the best, or you take the majority answer. It can improve accuracy on hard questions but multiplies cost.

## How agents share information

| Method | Notes |
| --- | --- |
| **Messages** | pass text between agents (simple) |
| **Shared state** | a common object (a graph's state) that agents read and update |
| **Shared memory / files** | notes, documents, a database |

Pass **summaries and results**, not whole conversations, to keep context small.

## Risks

- **Compounding errors**: a small mistake from one agent is trusted by the next.
- **Loops**: agents asking each other forever; set round limits.
- **Cost**: three agents can mean three to ten times the tokens.
- **Hard to debug**: use tracing so you can see each agent's inputs and outputs.
- **Security**: if one agent reads untrusted content, treat everything it passes on as untrusted.

## When to choose what

| Situation | Use |
| --- | --- |
| a simple task | one agent |
| distinct roles and tools | supervisor with workers |
| fixed stages | pipeline (workflow) |
| different expertise by topic | handoff or router |
| quality matters most | maker plus checker |

:::interview Single agent or multi-agent?
Use a single agent with good tools by default. Use multiple agents when roles, tools or context are clearly different, because more agents add cost, latency and failure modes.
:::
