---
title: Prompting, RAG or fine-tuning, and how to test an LLM app
summary: Choose the right way to adapt a model to your task, and build a small test set so you know whether your app really works.
takeaways:
- Try prompting first, then RAG for knowledge, and fine-tuning only for style or behaviour you cannot get otherwise
- You cannot improve what you do not measure: build a test set of real questions
- Check answers automatically where you can, and by people where you cannot
---
## Three ways to adapt a model

| Approach | What it changes | Cost and effort |
| --- | --- | --- |
| **Prompting** | the instructions and examples you send | free and instant |
| **RAG** | the **knowledge** the model can use | moderate: needs documents and a search system |
| **Fine-tuning** | the model's own **behaviour or style** | highest: needs good training data and training |

## Which one when

| Your problem | Best first choice |
| --- | --- |
| the answers are the wrong tone or format | **prompting** (instructions, examples, output format) |
| the model does not know your data, or the data changes | **RAG** |
| you need answers with sources for checking | **RAG** |
| a very specific style or task format that prompts cannot reach, and you have hundreds of good examples | **fine-tuning** (LoRA, see the deep learning course) |
| you want a smaller, cheaper model to do one narrow job well | **fine-tuning** |
| it needs to do things (search, calculate, call APIs) | **tools and agents** (next course) |

A common mistake is to fine-tune to **add knowledge**. Fine-tuning teaches style and patterns, not reliable facts. For facts, use RAG.

## How to test an LLM app

Normal software gives the same output every time, so a test can check equality. LLM output varies, so you build an **evaluation set** instead:

| Step | What to do |
| --- | --- |
| 1. collect **real questions** | 30 to 100 from real users, including awkward and off-topic ones |
| 2. write the **expected result** | the facts that must appear, or the source that must be used, or "should refuse" |
| 3. run your app on all of them | and record the answers |
| 4. **score** each answer | automatically where possible, by a person otherwise |
| 5. fix a failure and **rerun everything** | make sure you did not break other cases |

## A tiny evaluation harness

```python
test_cases = [
    {"question": "What attendance do I need to write the exams?", "must_include": ["75"], "must_not_include": []},
    {"question": "When is the semester fee due?", "must_include": ["10th"], "must_not_include": []},
    {"question": "Who won the cricket match?", "must_include": ["could not find"], "must_not_include": []},
    {"question": "What is the late fee?", "must_include": ["500"], "must_not_include": ["1000"]},
]

def my_app(question):
    """A stand-in for your real LLM app, so this example runs offline."""
    answers = {
        "What attendance do I need to write the exams?": "You need at least 75 percent attendance [1].",
        "When is the semester fee due?": "The fee is due by the 10th of the month the semester begins [2].",
        "Who won the cricket match?": "I could not find this in the documents.",
        "What is the late fee?": "A late fee of 1000 rupees applies [2].",          # a deliberately wrong answer
    }
    return answers[question]

passed = 0
for case in test_cases:
    answer = my_app(case["question"]).lower()
    ok = all(word.lower() in answer for word in case["must_include"]) and not any(word.lower() in answer for word in case["must_not_include"])
    passed += ok
    print(("PASS" if ok else "FAIL"), "|", case["question"])

print(f"\n{passed} of {len(test_cases)} tests passed")
```

```output
PASS | What attendance do I need to write the exams?
PASS | When is the semester fee due?
PASS | Who won the cricket match?
FAIL | What is the late fee?

3 of 4 tests passed
```

The harness caught the wrong late fee (1000 instead of 500). Run it after **every** change to the prompt, model or documents, and the failures tell you exactly what broke.

## Other ways to score

| Method | Use |
| --- | --- |
| **keyword and format checks** (above) | facts, numbers, JSON validity |
| **source checks** | did the answer cite the right document? |
| **LLM-as-judge** | another model grades answers against a rubric; fast, but it has biases, so spot-check it by hand |
| **human review** | the gold standard for tone and usefulness; sample regularly |
| **user feedback** (thumbs up and down) | find real problems after launch |

## What to measure

| Measure | Question |
| --- | --- |
| **accuracy** | is the answer correct? |
| **groundedness** | does the answer follow the sources, with nothing invented? |
| **refusal quality** | does it say "I do not know" when it should? |
| **latency** | how long does a user wait? |
| **cost per answer** | is it affordable at scale? |
| **safety** | does it resist misuse (the next lesson)? |

:::tip
Start the test set on day one with just ten questions and keep adding every real failure you find. After a month it is your most valuable asset.
:::
