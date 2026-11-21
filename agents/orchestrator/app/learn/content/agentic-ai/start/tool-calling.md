---
title: Tool calling (function calling)
summary: Give a model the ability to act: describe tools with a schema, let the model request a call, run it safely in your code and return the result.
takeaways:
- The model never runs anything; it asks your code to call a tool, and your code decides whether to
- A tool needs a name, a description and a schema for its inputs
- Validate every call and return clear errors, so the model can correct itself
---
## The key idea

A language model can only produce text. **Tool calling** turns that text into actions in three steps:

1. You **describe the tools** to the model (name, purpose, input fields).
2. The model replies with a **request to call a tool**, as structured data, for example `{"tool": "get_exam_date", "arguments": {"subject": "maths"}}`.
3. **Your code** checks the request, runs the real function, and sends the **result** back. The model then continues.

The model decides **what** to call. Your code decides **whether and how** it runs. That is where safety lives.

## Describe the tools

A tool is a normal function plus a description. The description is part of the prompt: the model chooses tools by reading it, so write it as clearly as an instruction.

```python
import ast
import operator
from datetime import date

EXAM_DATES = {"maths": "2026-12-10", "physics": "2026-12-14", "chemistry": "2026-12-18"}

def get_exam_date(subject):
    return EXAM_DATES[subject.lower()]

def days_between(start, end):
    return (date.fromisoformat(end) - date.fromisoformat(start)).days

ALLOWED = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg}

def calculator(expression):
    """A safe calculator: it understands only numbers and + - * / **, never arbitrary code."""
    def evaluate(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED:
            return ALLOWED[type(node.op)](evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED:
            return ALLOWED[type(node.op)](evaluate(node.operand))
        raise ValueError("only numbers and + - * / ** are allowed")
    return evaluate(ast.parse(expression, mode="eval").body)

TOOLS = {
    "get_exam_date": {"function": get_exam_date, "required": ["subject"],
                      "description": "Look up the exam date for a subject. Returns a date like 2026-12-10."},
    "days_between": {"function": days_between, "required": ["start", "end"],
                     "description": "Number of days from a start date to an end date (both as YYYY-MM-DD)."},
    "calculator": {"function": calculator, "required": ["expression"],
                   "description": "Evaluate a plain arithmetic expression such as 640 * 0.15."},
}
print("tools available:", sorted(TOOLS))
```

```output
tools available: ['calculator', 'days_between', 'get_exam_date']
```

Notice that `calculator` does **not** use `eval()`. Running arbitrary text from a model as code would let anyone who can influence the model run anything on your machine. The tool accepts only arithmetic.

## Run a call safely

Your code sits between the model and the function, and checks everything:

```python
def call_tool(name, arguments):
    tool = TOOLS.get(name)
    if tool is None:
        return f"error: unknown tool {name!r}. Available tools: {sorted(TOOLS)}"
    missing = [field for field in tool["required"] if field not in arguments]
    if missing:
        return f"error: missing arguments {missing}"
    try:
        return str(tool["function"](**arguments))
    except Exception as error:                      # a failing tool must not crash the agent
        return f"error: {type(error).__name__}: {error}"

requests = [
    {"tool": "get_exam_date", "arguments": {"subject": "Maths"}},
    {"tool": "days_between", "arguments": {"start": "2026-11-21", "end": "2026-12-10"}},
    {"tool": "calculator", "arguments": {"expression": "640 * 0.15"}},
    {"tool": "calculator", "arguments": {"expression": "__import__('os').system('dir')"}},     # a dangerous request
    {"tool": "get_exam_date", "arguments": {"subject": "history"}},                            # a subject we do not have
    {"tool": "send_email", "arguments": {"to": "all"}},                                        # a tool that does not exist
    {"tool": "days_between", "arguments": {"start": "2026-11-21"}},                            # a missing argument
]
for request in requests:
    print(f"{request['tool']}({request['arguments']})\n    -> {call_tool(request['tool'], request['arguments'])}")
```

```output
get_exam_date({'subject': 'Maths'})
    -> 2026-12-10
days_between({'start': '2026-11-21', 'end': '2026-12-10'})
    -> 19
calculator({'expression': '640 * 0.15'})
    -> 96.0
calculator({'expression': "__import__('os').system('dir')"})
    -> error: ValueError: only numbers and + - * / ** are allowed
get_exam_date({'subject': 'history'})
    -> error: KeyError: 'history'
send_email({'to': 'all'})
    -> error: unknown tool 'send_email'. Available tools: ['calculator', 'days_between', 'get_exam_date']
days_between({'start': '2026-11-21'})
    -> error: missing arguments ['end']
```

The first three calls work. The dangerous expression is **refused**, not executed. The other three fail with a message, so the model can fix its next attempt. Returning errors as text, instead of crashing, is what lets an agent recover.

The messages are not equally helpful. The unknown subject gives a terse `KeyError: 'history'`, while the unknown tool lists the tools that exist. A good tool returns a message the model can act on, for example "no exam date for history; known subjects: maths, physics, chemistry".

## With a real model

The tool descriptions are sent as a **JSON schema**, and the model answers with a tool request. With the Anthropic library the shape is:

```py
tools = [{
    "name": "get_exam_date",
    "description": "Look up the exam date for a subject. Returns a date like 2026-12-10.",
    "input_schema": {"type": "object", "properties": {"subject": {"type": "string"}}, "required": ["subject"]},
}]

reply = client.messages.create(model="claude-sonnet-5-5", max_tokens=500, tools=tools,
                               messages=[{"role": "user", "content": "When is my maths exam?"}])

if reply.stop_reason == "tool_use":
    block = next(b for b in reply.content if b.type == "tool_use")           # the model's request
    result = call_tool(block.name, block.input)                             # YOUR code runs it
    follow_up = client.messages.create(
        model="claude-sonnet-5-5", max_tokens=500, tools=tools,
        messages=[
            {"role": "user", "content": "When is my maths exam?"},
            {"role": "assistant", "content": reply.content},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": block.id, "content": result}]},
        ],
    )
    print(follow_up.content[0].text)
```

Other providers use almost the same idea under names such as "function calling". Check the current documentation for exact field names.

## Writing good tools

| Rule | Why |
| --- | --- |
| one clear job per tool | easier for the model to choose |
| a precise **description** with an example | the model reads it like an instruction |
| few, well-named parameters with types | fewer mistakes |
| return short, useful text (not huge dumps) | saves tokens and attention |
| return **errors as messages** | the model can retry |
| **validate and limit** everything | the model can be wrong or be tricked |
| separate **read** tools from **write** tools | writes need more care and approval |

:::warning
A tool is a power you hand to a model that can be wrong or manipulated. Never give it a tool that can do more than the task needs (no raw shell, no `eval`, no unrestricted database writes).
:::
