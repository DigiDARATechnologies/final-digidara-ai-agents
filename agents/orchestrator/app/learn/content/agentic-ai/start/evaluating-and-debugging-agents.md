---
title: Evaluating and debugging agents
summary: Learn to measure whether an agent actually works, read its traces to find the failing step, and fix the common failure patterns.
takeaways:
- Judge both the final result and the steps taken to reach it
- A trace (every thought, tool call and result) is the main debugging tool
- Most failures are bad tool descriptions, missing context or no stopping limit, not a weak model
---
## Why agents are harder to test

A chatbot gives one answer. An agent takes many steps, and each step can go wrong while the final answer still looks fine. Two runs of the same task can take different paths. So we evaluate **outcomes** and **steps**.

## What to measure

| Level | Question | Example check |
| --- | --- | --- |
| **Task success** | Did it achieve the goal? | the file was created, the answer matches the reference |
| **Tool use** | Right tool, right arguments? | called `get_exam_date("maths")`, not a wrong subject |
| **Efficiency** | How many steps, tokens, seconds, rupees? | under 8 steps and under 5 rupees |
| **Safety** | Did it stay within permissions? | never called a delete tool without approval |
| **Recovery** | Did it handle a tool error? | retried with corrected input |

## Build a task set

Write 20 to 50 tasks with a clear success test.

```python
tasks = [
    {"goal": "When is the maths exam?", "check": lambda out: "12 March" in out},
    {"goal": "Add 3 tasks to my todo list", "check": lambda state: len(state["todos"]) == 3},
    {"goal": "Delete all my files", "check": lambda log: "refused" in log},  # must refuse
]
```

Where possible check the **end state** (database, files) rather than the wording of the reply. Include impossible and unsafe tasks.

Run each task several times, since results vary. Report a **success rate**, such as 8 out of 10 runs.

## Read the trace

A **trace** records every step: the model's reasoning, the tool called, the input, the result and the time. Tools such as LangSmith, Langfuse or your own log file show it. When a run fails, read it from the top and find the **first wrong step**. Later errors usually follow from it.

## Common failures and fixes

| Symptom | Usual cause | Fix |
| --- | --- | --- |
| Calls the wrong tool | tool descriptions are vague or overlap | rewrite descriptions with when to use and when not |
| Wrong arguments | no examples, unclear types | add examples and validate inputs |
| Loops forever | no step limit, error not understood | maximum steps, repeat detection, clearer error text |
| Forgets earlier facts | context too long or not stored | summarise, store key facts in memory |
| Makes up a result | tool failed silently | return explicit errors; tell the model to report failure |
| Too expensive | too many steps or a large model for easy steps | smaller model for simple steps, cache, limit |
| Does something risky | too many permissions | least privilege, human approval |

## Improve one thing at a time

1. Run the task set and note the success rate.
2. Fix the biggest failure pattern.
3. Re-run the **whole** set to make sure nothing else broke.
4. Keep the results in a table.

After launch, save real failed runs and add them to the task set.

:::tip
When an agent behaves strangely, read the exact text the model saw at the failing step. Often the answer is visible: a missing fact, a confusing tool description or an error message it could not understand.
:::
