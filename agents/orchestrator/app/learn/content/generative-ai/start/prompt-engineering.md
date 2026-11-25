---
title: Prompt engineering
summary: Write prompts that get reliable results: clear instructions, roles, examples, structure and output formats, with templates you can reuse.
takeaways:
- A good prompt states the task, the context, the format and the limits
- Examples (few-shot) teach the model the pattern you want
- Ask for a structured format such as JSON and validate it in code
---
## A prompt is a specification

The model can only use what you tell it. Vague prompts get vague answers. A reliable prompt has five parts:

| Part | Question it answers | Example |
| --- | --- | --- |
| **Role** | who should the model act as? | "You are a friendly Python tutor for first-year students." |
| **Task** | what exactly must it do? | "Explain the error message below." |
| **Context** | what does it need to know? | the code, the error, the learner's level |
| **Format** | what should the answer look like? | "Use at most 5 sentences, then show the fixed code." |
| **Limits** | what must it avoid? | "Do not use jargon. If you are unsure, say so." |

Compare:

| Weak | Strong |
| --- | --- |
| "Explain loops." | "Explain Python `for` loops to a first-year student in 5 sentences, with one example about marks, and end with one practice question." |
| "Fix my code." | "This Python function should return the average of a list but raises ZeroDivisionError for an empty list. Fix it, explain the change in two sentences, and return only the corrected function." |

## Build prompts from a template

Do not retype prompts. Use a template function so every call is consistent:

```python
def build_prompt(role, task, context, format_rules, limits):
    return (
        f"You are {role}.\n\n"
        f"Task: {task}\n\n"
        f"Context:\n{context}\n\n"
        f"Answer format: {format_rules}\n"
        f"Rules: {limits}"
    )

prompt = build_prompt(
    role="a friendly Python tutor for first-year students",
    task="Explain the error in the code below.",
    context="def average(marks):\n    return sum(marks) / len(marks)\n\nprint(average([]))\n\nZeroDivisionError: division by zero",
    format_rules="at most 4 sentences, then the corrected code",
    limits="use simple words; if you are not sure, say so",
)
print(prompt)
```

```output
You are a friendly Python tutor for first-year students.

Task: Explain the error in the code below.

Context:
def average(marks):
    return sum(marks) / len(marks)

print(average([]))

ZeroDivisionError: division by zero

Answer format: at most 4 sentences, then the corrected code
Rules: use simple words; if you are not sure, say so
```

## Show examples (few-shot prompting)

Showing the model a few examples of input and the output you want often works better than describing it. This is **few-shot prompting**.

```python
examples = [
    ("The delivery was late and the box was damaged.", "negative"),
    ("Great quality, works perfectly!", "positive"),
    ("It is okay, nothing special.", "neutral"),
]

def few_shot_prompt(text):
    lines = ["Classify the review as positive, negative or neutral. Reply with one word.", ""]
    for example_text, label in examples:
        lines.append(f"Review: {example_text}\nLabel: {label}\n")
    lines.append(f"Review: {text}\nLabel:")
    return "\n".join(lines)

print(few_shot_prompt("Battery lasts two days, very happy."))
```

```output
Classify the review as positive, negative or neutral. Reply with one word.

Review: The delivery was late and the box was damaged.
Label: negative

Review: Great quality, works perfectly!
Label: positive

Review: It is okay, nothing special.
Label: neutral

Review: Battery lasts two days, very happy.
Label:
```

The examples fix the labels, the format and the one-word style. Choose examples that are **varied** and **correct**: the model copies their mistakes too.

## Ask for structured output, then validate it

For software to use the answer, ask for **JSON** and **check it in code**. Never trust that the model followed the format:

```python
import json

raw_answers = [
    '{"sentiment": "positive", "confidence": 0.93}',                                   # perfect
    '```json\n{"sentiment": "negative", "confidence": 0.71}\n```',                    # wrapped in a code fence
    'Sure! The sentiment is positive.',                                                # ignored the format
    '{"sentiment": "angry", "confidence": 2}',                                        # invalid values
]

def parse_answer(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()                         # remove a code fence
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, "not valid JSON"
    if data.get("sentiment") not in {"positive", "negative", "neutral"}:
        return None, "unknown sentiment label"
    if not 0 <= data.get("confidence", -1) <= 1:
        return None, "confidence must be between 0 and 1"
    return data, "ok"

for answer in raw_answers:
    data, status = parse_answer(answer)
    print(f"{status:<36} <- {answer[:44]!r}")
```

```output
ok                                   <- '{"sentiment": "positive", "confidence": 0.93'
ok                                   <- '```json\n{"sentiment": "negative", "confidenc'
not valid JSON                       <- 'Sure! The sentiment is positive.'
unknown sentiment label              <- '{"sentiment": "angry", "confidence": 2}'
```

One of four answers was usable as it came, one needed its code fence removed, and two were rejected. In a real application you would **retry** or fall back when validation fails. Many APIs also offer built-in structured output modes that reduce these failures, but you should still validate.

## Techniques that help

| Technique | How | When |
| --- | --- | --- |
| **step by step reasoning** | "Think through the problem step by step, then give the final answer." | maths, logic, planning |
| **delimiters** | wrap pasted text in `"""` or `<document>` tags | separate your instructions from the data |
| **ask for sources or uncertainty** | "Quote the sentence that supports your answer." | reduce made-up facts |
| **break big tasks apart** | one prompt to outline, another to write each part | long or complex work |
| **iterate** | test the prompt on 10 to 20 varied inputs and fix the failures | always |

## Common mistakes

| Mistake | Fix |
| --- | --- |
| long, tangled prompts | short sections with clear labels |
| contradicting instructions | read the prompt as if you were the model |
| testing on only one example | build a small test set |
| assuming the model knows your context | state everything it needs |
| putting secrets in the prompt | prompts can leak; never include keys or private data you cannot share |

:::tip
Treat prompts like code: keep them in files, give them names and versions, and test every change on the same set of examples. A "better" prompt that fixes one case often breaks another.
:::
