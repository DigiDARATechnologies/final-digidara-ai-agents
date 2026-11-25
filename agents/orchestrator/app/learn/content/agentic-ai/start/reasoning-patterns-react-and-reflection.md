---
title: Reasoning patterns: ReAct, plan-and-execute and reflection
summary: Learn the standard ways to structure an agent's thinking: ReAct, plan then execute, reflection and routing.
takeaways:
- ReAct alternates reasoning and acting, using each tool result to decide the next step
- Plan-and-execute writes the plan first, which suits longer, predictable tasks
- Reflection lets the agent check and improve its own draft
---
## Patterns, not magic

Most agents are built from a few reusable patterns. Knowing them lets you pick the simplest one that works.

## 1. ReAct: reason and act

The model repeats: **Thought** (what do I need?), **Action** (call a tool), **Observation** (read the result), until it can answer.

```text
Question: Which is bigger, the population of Chennai or Madurai?
Thought: I need both populations.
Action: search("population of Chennai")
Observation: about 11 million (metro)
Action: search("population of Madurai")
Observation: about 1.5 million
Thought: 11 million is more than 1.5 million.
Answer: Chennai is much bigger.
```

Strength: flexible, each step uses fresh information. Weakness: it can wander or loop, so set a step limit.

## 2. Plan and execute

First write the **whole plan**, then run each step. A cheaper model can execute steps while a stronger one plans.

```text
Goal: research report on electric scooters
Plan: 1) search market size  2) search top 3 brands  3) find safety rules  4) write the report
Execute step 1 ... step 2 ... step 3 ... step 4
```

Good when the steps are fairly predictable. Allow **re-planning** if a step fails or new facts change the plan.

## 3. Reflection (self-critique)

The agent writes a draft, then a second pass **reviews** it against a checklist and improves it.

```python
draft = llm("Write a cover letter for this job: ...")
for _ in range(2):                                   # at most two rounds
    critique = llm(f"Review this letter against the job. List specific problems.\n\n{draft}")
    if "no problems" in critique.lower():
        break
    draft = llm(f"Improve the letter using this feedback.\n\nLetter:\n{draft}\n\nFeedback:\n{critique}")
```

Reflection helps quality, especially when the critic has **clear criteria** or a **tool result** (a test run, a validator). A model grading its own work with no outside check can approve mistakes, so prefer objective checks where possible.

## 4. Routing

A first model call decides **which path or specialist** handles the request (billing, technical, general), then the specialist runs. Simple, cheap and predictable.

## 5. Tool-use with verification

After producing an answer, run a **verifier** tool: execute the generated code, validate the JSON, check the sum with a calculator, confirm a URL exists.

## Choosing a pattern

| Task | Pattern |
| --- | --- |
| open-ended question needing searches | ReAct |
| long task with known stages | plan and execute |
| writing, code, analysis needing quality | reflection plus verification |
| many kinds of requests | routing |
| fixed steps, no decisions | a plain workflow (no agent) |

## Control the cost

Each loop costs tokens and time. Set a **maximum number of steps**, stop when the goal is met, and log every step so you can see why it behaved as it did.

:::remember
Start with the simplest pattern. Add planning or reflection only when tests show the simple version is not good enough.
:::
