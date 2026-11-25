---
title: Designing good tools for agents
summary: Write tools the model uses correctly: clear names, precise descriptions, small outputs and helpful errors.
takeaways:
- The tool description is the instruction manual the model reads
- Few, focused, well-named tools beat many overlapping ones
- Return short, useful results and errors the model can act on
---
## The model only sees what you write

The agent chooses tools by reading their **name, description and parameters**. Most agent failures that look like "the model is dumb" are really **unclear tools**.

## Principles

### 1. One clear purpose

`get_order_status(order_id)` is better than `order_tool(action, data)`. Small focused tools are easier to choose and to validate.

### 2. Names and descriptions say when to use it

Bad: `search` - "Searches."
Good: `search_handbook` - "Search the college handbook for rules about attendance, fees, hostel and exams. Use this for policy questions. Do not use it for marks or timetable."

Mention **what it does, when to use it and when not to**.

### 3. Precise parameters

Give types, enums and examples, and mark required fields.

```python
{
  "name": "create_ticket",
  "description": "Create a support ticket. Use only after the user confirms the issue.",
  "input_schema": {
    "type": "object",
    "properties": {
      "title": {"type": "string", "description": "Short summary, under 80 characters"},
      "priority": {"type": "string", "enum": ["low", "medium", "high"]},
      "order_id": {"type": "string", "description": "Order id like ORD-1042, if the issue is about an order"}
    },
    "required": ["title", "priority"]
  }
}
```

### 4. Small, relevant outputs

A tool that returns a 50,000 character page wastes context and confuses the model. Return the **useful part**: limit rows, trim text, return the fields needed, and say how to get more ("showing 5 of 120, ask for the next page").

### 5. Errors the model can act on

Bad: `Error 500`.
Good: `No order found with id ORD-9999. Order ids look like ORD-1042. Ask the user to check the id.`

### 6. Safe by design

- **Read-only** tools where possible.
- Validate every input in code; never trust the model's arguments (SQL, file paths, amounts).
- Separate **dangerous actions** into their own tools that require approval.
- Return an **idempotent** result so a retry does not repeat the action.

### 7. Few tools

Ten well-described tools are easier than fifty. If there are many, group them by task and give the agent only the group it needs for the current step.

## Test your tools

Write 10 to 20 realistic requests and check that the agent picks the right tool with the right arguments. When it fails, change the **description** first, not the model.

## Checklist

- clear name and one purpose
- description with when to use and when not
- typed parameters with examples
- compact output
- helpful error messages
- input validation and least privilege

:::tip
Read your tool descriptions as if you were a new employee who has never seen the system. If you would be unsure which tool to use, the model will be too.
:::
