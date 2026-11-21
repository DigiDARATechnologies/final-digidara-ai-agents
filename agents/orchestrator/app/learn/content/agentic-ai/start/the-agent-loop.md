---
title: The agent loop, step by step
summary: Build a working agent in a few lines: the think, act, observe loop with a step limit, error recovery and a trace you can read.
takeaways:
- An agent is a loop: ask the model, run the tool it chose, add the result, ask again
- A maximum number of steps stops runaway loops
- Returning errors lets the agent correct itself instead of failing
---
## What we will build

A small agent that answers: *"My maths exam is on 2026-12-10 and today is 2026-11-21. How many days are left, and what is 15% of 640 marks?"* It needs **two tools**: one for dates, one for arithmetic.

To run offline and see exactly what happens, the "model" here is a **scripted stand-in** that behaves like a model deciding the next action from what it has seen. With a real LLM you replace this one function and nothing else changes.

## The tools (from the last lesson)

```python
import ast
import operator
from datetime import date

ALLOWED = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg}

def calculator(expression):
    def evaluate(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED:
            return ALLOWED[type(node.op)](evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED:
            return ALLOWED[type(node.op)](evaluate(node.operand))
        raise ValueError("only numbers and + - * / ** are allowed")
    return evaluate(ast.parse(expression, mode="eval").body)

def days_between(start, end):
    return (date.fromisoformat(end) - date.fromisoformat(start)).days

TOOLS = {"calculator": calculator, "days_between": days_between}

def call_tool(name, arguments):
    if name not in TOOLS:
        return f"error: unknown tool {name!r}"
    try:
        return str(TOOLS[name](**arguments))
    except Exception as error:
        return f"error: {type(error).__name__}: {error}"
```

## The stand-in model

It looks at the tool results so far and decides the next action. It makes a **deliberate mistake** first so we can watch the agent recover.

```python
def scripted_model(history):
    results = [m["content"] for m in history if m["role"] == "tool"]
    if len(results) == 0:
        return {"type": "tool_call", "tool": "days_between", "arguments": {"start": "2026-11-21", "end": "2026-12-10"}}
    if len(results) == 1:
        return {"type": "tool_call", "tool": "calculator", "arguments": {"expression": "640 * 15%"}}       # a mistake: % is not allowed
    if results[-1].startswith("error"):
        return {"type": "tool_call", "tool": "calculator", "arguments": {"expression": "640 * 0.15"}}       # it fixes the mistake
    return {"type": "final", "text": f"There are {results[0]} days left, and 15% of 640 marks is {results[-1]}."}
```

## The loop

```python
def run_agent(goal, model, max_steps=6):
    history = [{"role": "user", "content": goal}]
    for step in range(1, max_steps + 1):
        action = model(history)                                         # THINK: the model decides
        if action["type"] == "final":
            print(f"step {step}: FINAL ANSWER -> {action['text']}")
            return action["text"]
        print(f"step {step}: ACT      {action['tool']}({action['arguments']})")
        observation = call_tool(action["tool"], action["arguments"])    # ACT: our code runs the tool
        print(f"         OBSERVE  {observation}")
        history.append({"role": "assistant", "content": str(action)})
        history.append({"role": "tool", "content": observation})        # OBSERVE: the result goes back to the model
    print(f"stopped: reached the limit of {max_steps} steps without an answer")
    return None

goal = "My maths exam is on 2026-12-10 and today is 2026-11-21. How many days are left, and what is 15% of 640 marks?"
run_agent(goal, scripted_model)
```

```output
step 1: ACT      days_between({'start': '2026-11-21', 'end': '2026-12-10'})
         OBSERVE  19
step 2: ACT      calculator({'expression': '640 * 15%'})
         OBSERVE  error: SyntaxError: unexpected EOF while parsing (<unknown>, line 1)
step 3: ACT      calculator({'expression': '640 * 0.15'})
         OBSERVE  96.0
step 4: FINAL ANSWER -> There are 19 days left, and 15% of 640 marks is 96.0.
```

Read the trace like a story: the agent found the days, tried a calculation that was rejected (`640 * 15%` is not valid arithmetic), **saw the error**, tried again with `640 * 0.15`, and then wrote the final answer. That recovery is the whole value of an agent over a single fixed call. The error came back as text, and the model **used it**.

## Always have a stop

Models can get stuck, repeating the same call forever. A **step limit** is essential:

```python
def stubborn_model(history):
    return {"type": "tool_call", "tool": "calculator", "arguments": {"expression": "1 / 0"}}      # never gives a final answer

run_agent("Divide one by zero.", stubborn_model, max_steps=3)
```

```output
step 1: ACT      calculator({'expression': '1 / 0'})
         OBSERVE  error: ZeroDivisionError: division by zero
step 2: ACT      calculator({'expression': '1 / 0'})
         OBSERVE  error: ZeroDivisionError: division by zero
step 3: ACT      calculator({'expression': '1 / 0'})
         OBSERVE  error: ZeroDivisionError: division by zero
stopped: reached the limit of 3 steps without an answer
```

Without the limit this loop would run (and spend money) forever. Real agents also add:

| Safeguard | Purpose |
| --- | --- |
| **maximum steps** | stop runaway loops |
| **token and cost budget** | stop runaway bills |
| **timeout** | stop a hung tool |
| **repeat detection** | stop when the same call fails again and again |
| **human approval** for risky steps | the next lessons |

## With a real model

The loop is identical. Only the `model(history)` function changes: it sends the messages and tool descriptions to an LLM API and turns the reply into either a `tool_call` or a `final` answer (see the tool-calling lesson). Many libraries (the OpenAI Agents SDK, the Claude Agent SDK, LangGraph, and others) package this loop for you, but understanding it makes every one of them clear.

## Why agents fail

| Failure | Cause | Fix |
| --- | --- | --- |
| loops forever | no stop condition | step limit, repeat detection |
| picks the wrong tool | unclear tool descriptions | better names and descriptions |
| bad tool arguments | the model guessed | validate, return clear errors |
| forgets earlier results | too much history | memory management (next lesson) |
| confident wrong final answer | no check | verify with tools, add a reviewer step, test on examples |
| does something harmful | too much power | permissions and approval (later lesson) |

:::interview
**Interviewers often ask:** "How does an AI agent work?" It runs a loop: the model looks at the goal and everything so far and either calls a tool or gives a final answer; the application runs the tool and feeds the result back; the loop repeats until the answer is ready or a step limit is hit.
:::
