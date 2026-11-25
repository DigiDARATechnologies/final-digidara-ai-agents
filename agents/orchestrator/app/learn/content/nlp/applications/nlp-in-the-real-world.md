---
title: NLP in the real world: challenges and Indian languages
summary: Handle messy text, mixed languages, bias and privacy when taking NLP from a notebook to real users.
takeaways:
- Real text has typos, slang, emojis and mixed languages
- Data quality and privacy matter more than the model choice
- Models inherit bias from their training data
---
## Real text is messy

Tutorial data is clean. Real messages look like: "plz refund my mony asap!!! 😡", "order nahi aaya, kab milega?" (Hinglish), or contain OCR errors from scanned documents.

| Challenge | Example | Approach |
| --- | --- | --- |
| Typos and slang | "gr8", "thnx" | normalisation, character-level or sub-word models |
| Emojis | "😡" signals anger | keep them, they carry sentiment |
| **Code-mixing** | Hinglish, Tanglish | multilingual models, add mixed data |
| Sarcasm | "Great, another delay" | needs context; hard even for LLMs |
| Negation | "not good" | use models that read order (BERT) |
| Domain words | "EMI", "KYC" | add domain training data |
| Long documents | contracts | split into chunks, summarise |

## Indian languages

India has 22 scheduled languages and many scripts. Challenges: less labelled data than English, rich word forms, many scripts, and transliteration (Hindi written in English letters).

Helpful resources: **AI4Bharat** (IndicBERT, IndicTrans2, IndicNLP), multilingual models (**mBERT, XLM-R**), and multilingual LLMs. Start with a multilingual model, test on **your** language, and collect a small labelled set to fine-tune.

## Data matters most

- **Label quality**: two people should mostly agree on a label. Write labelling guidelines.
- **Class balance**: collect more of the rare class or use class weights.
- **Fresh data**: language changes, so re-check the model every few months (**data drift**).
- **Enough examples**: often a few hundred good examples per class beat thousands of noisy ones.

## Bias and fairness

A model learns from human text and copies its biases. A sentiment model may rate sentences with some names or dialects as more negative. Test with **paired examples** that differ only in a name or group, compare the scores, and fix the data or add checks when they differ.

## Privacy

Text often contains **personal data**: names, phone numbers, emails, Aadhaar numbers. Before storing or training:

- **mask** or remove personal identifiers (regex plus NER)
- keep only what you need, and get permission
- do not send private text to a public API without approval

```python
import re

def mask_personal(text):
    text = re.sub(r"\b\d{10}\b", "[PHONE]", text)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[EMAIL]", text)
    return text

print(mask_personal("Call 9876543210 or mail asha@example.com"))
```

```output
Call [PHONE] or mail [EMAIL]
```

## From notebook to product

1. Wrap the model in an API (Flask or FastAPI).
2. Log inputs and outputs (masked) to find failures.
3. Add a **fallback** (a human, or "I am not sure") when confidence is low.
4. Re-evaluate on fresh data regularly.

:::remember
In real NLP projects, data collection, cleaning, labelling and monitoring take most of the time. The model is the easy part.
:::
