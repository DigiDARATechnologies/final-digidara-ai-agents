---
title: Structured output and function calling
summary: Make an LLM return valid JSON you can trust, and let it request function calls your code runs.
takeaways:
- Apps need data, not paragraphs: ask for JSON that matches a schema
- Validate every output; models can still break the format
- Function calling lets the model choose a function and its arguments
---
## Why structure matters

A program cannot reliably read "The invoice number is 4471 and the total is about 2,500 rupees". It needs `{"invoice": "4471", "total": 2500}`. So we ask the model for **structured output**.

## Ask for JSON and validate it

```python
import json
from pydantic import BaseModel, ValidationError

class Invoice(BaseModel):
    invoice_number: str
    total: float
    currency: str

prompt = (
    "Extract the invoice details from the text. "
    "Reply with JSON only, with keys invoice_number, total, currency.\n\n"
    "Text: Invoice 4471 from Acme Traders, amount due Rs. 2,500."
)

raw = call_llm(prompt)                  # your function that calls the API

try:
    data = Invoice.model_validate_json(raw)
    print(data.total)
except ValidationError as error:
    print("Bad output, retry or fall back:", error)
```

(Display only: `call_llm` is your API function.) **Never trust the format blindly.** Validate with Pydantic or a JSON schema, and **retry** with the error message when validation fails.

## Built-in structured output

Most providers can **force** the output to follow a JSON schema, which removes most format errors.

```python
response = client.responses.create(
    model="your-model",
    input="Invoice 4471 from Acme Traders, amount due Rs. 2,500.",
    text={"format": {"type": "json_schema", "name": "invoice", "schema": Invoice.model_json_schema()}},
)
```

(The exact parameter names differ between providers; check the documentation.)

## Function calling (tool calling)

You describe functions with a name, a description and a parameter schema. The model does **not run them**; it replies with *which function to call and the arguments*, your code runs it, and you send the result back (the tool calling lesson in Agentic AI shows the full loop).

```python
tools = [{
    "name": "get_weather",
    "description": "Get the current weather for a city.",
    "input_schema": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
}]

# the model answers a question like "Do I need an umbrella in Pune?" with:
# {"name": "get_weather", "input": {"city": "Pune"}}
```

## Good practice

| Tip | Why |
| --- | --- |
| Give each field a **short description** | the model fills it more accurately |
| Use **enums** for fixed choices | `"status": "paid" or "unpaid"` |
| Make unknown fields **nullable** | stops the model inventing values |
| Keep the schema **small** | simpler schemas fail less |
| **Validate and retry** | handle the rare failure |
| Set **temperature low** | consistent structure |

## Typical uses

Extracting fields from invoices, resumes and emails; classifying tickets; turning a request into a database query; filling forms; routing a message to the right tool.

:::warning
If the output controls something real (a payment, a delete), validate the values and check them against your own rules. Never run model-written SQL or code without limits.
:::
