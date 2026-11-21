---
title: Text classification and named entity recognition
summary: Sort messages into several categories with TF-IDF and Naive Bayes, and pull names, dates and amounts out of text with entity recognition.
takeaways:
- Multi-class text classification works just like sentiment analysis, with more than two labels
- Naive Bayes is a fast, strong baseline for text
- NER finds the people, places, dates and amounts inside text
---
## Classifying into several categories

A company gets thousands of support messages and wants each sent to the right team: **billing**, **delivery**, **technical** or **account**.

```python
messages = [
    ("I was charged twice for my order", "billing"), ("please refund my payment", "billing"), ("my invoice shows the wrong amount", "billing"),
    ("the card payment failed but money was deducted", "billing"), ("I need a bill for last month", "billing"), ("why is there an extra charge on my statement", "billing"),
    ("refund has not reached my bank account", "billing"), ("payment was deducted twice", "billing"), ("send me the invoice for my purchase", "billing"),
    ("the price charged is higher than shown", "billing"),
    ("my parcel has not arrived yet", "delivery"), ("the courier delivered to the wrong address", "delivery"), ("where is my package", "delivery"),
    ("delivery is delayed by a week", "delivery"), ("the package arrived damaged", "delivery"), ("can I change my shipping address", "delivery"),
    ("the courier did not call before delivery", "delivery"), ("my order shows delivered but I did not receive it", "delivery"),
    ("when will my parcel reach me", "delivery"), ("the delivery boy was rude", "delivery"),
    ("the app crashes when I open it", "technical"), ("I cannot upload a file", "technical"), ("the website is very slow", "technical"),
    ("the page shows error 500", "technical"), ("the video will not play", "technical"), ("the button does nothing when clicked", "technical"),
    ("the app freezes on the home screen", "technical"), ("download keeps failing", "technical"), ("the screen goes blank after the update", "technical"),
    ("notifications are not working on the app", "technical"),
    ("I forgot my password", "account"), ("how do I change my email address", "account"), ("please delete my account", "account"),
    ("I cannot log in to my profile", "account"), ("update my phone number", "account"), ("my account is locked", "account"),
    ("reset my login details", "account"), ("I want to change my username", "account"), ("verification email did not come", "account"),
    ("how do I close my profile", "account"),
]
texts = [m for m, _ in messages]
labels = [l for _, l in messages]
print(len(texts), "messages in", len(set(labels)), "categories")
```

```output
40 messages in 4 categories
```

## Train a classifier

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import cross_val_score
from sklearn.naive_bayes import MultinomialNB
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

models = {
    "Naive Bayes": make_pipeline(TfidfVectorizer(stop_words="english"), MultinomialNB()),
    "Logistic regression": make_pipeline(TfidfVectorizer(stop_words="english"), LogisticRegression(max_iter=1000)),
}
for name, model in models.items():
    scores = cross_val_score(model, texts, labels, cv=4)
    print(f"{name:<20} cross-validated accuracy {scores.mean():.2f}")
```

```output
Naive Bayes          cross-validated accuracy 0.65
Logistic regression  cross-validated accuracy 0.70
```

With only 40 short messages, both score about 65 to 70%. Random guessing among four categories would score 25%, so the models have learned something, but this is not good enough to use. That is a **real result for tiny data**, not a bug: each category has only ten examples and the messages share few words. Naive Bayes is very fast and is the classic first model for text; logistic regression is usually a little stronger as data grows.

```python
best = models["Logistic regression"].fit(texts, labels)
new_messages = ["my order is late", "refund the money", "app keeps freezing", "reset my login"]
for message, label in zip(new_messages, best.predict(new_messages)):
    print(f"{label:<10} <- {message}")
```

```output
billing    <- my order is late
billing    <- refund the money
technical  <- app keeps freezing
account    <- reset my login
```

Three of the four messages go to the right team. "My order is late" went to **billing** instead of delivery, because the only word it shares with the training messages is "order", and that word appears in a billing example ("charged twice for my order"). This is exactly the kind of mistake that tells you what to do next:

| Fix | Why it helps |
| --- | --- |
| collect **more examples** per category (hundreds, not ten) | the model sees more ways people say the same thing |
| add the misrouted messages to the training data with the right label | learn from real mistakes |
| look at the **confusion matrix** | see which categories get mixed up |
| try sentence embeddings or a pretrained transformer | match meaning, not just shared words |

## Named entity recognition (NER)

**NER** finds and labels real-world things in text: people, organisations, places, dates, money.

| Text | Entities found |
| --- | --- |
| "Priya joined Infosys in Chennai on 4 March for ₹6 lakh." | Priya (PERSON), Infosys (ORG), Chennai (PLACE), 4 March (DATE), ₹6 lakh (MONEY) |

Uses: pull the customer name and order number out of an email, extract amounts from invoices, tag news articles by company.

With **spaCy**, a ready-made NER model takes three lines:

```py
pip install spacy
python -m spacy download en_core_web_sm

import spacy
nlp = spacy.load("en_core_web_sm")
doc = nlp("Priya joined Infosys in Chennai on 4 March for 6 lakh rupees.")
for entity in doc.ents:
    print(entity.text, "->", entity.label_)
```

## Simple extraction with patterns

For entities with a fixed shape (emails, phone numbers, amounts), **regular expressions** are enough and need no model:

```python
import re

text = "Contact priya@example.com or 98765 43210. Invoice 4412 total Rs. 12,500 due on 14/03/2026."

print("emails :", re.findall(r"[\w.]+@[\w.]+\.\w+", text))
print("phones :", re.findall(r"\b\d{5}\s?\d{5}\b", text))
print("amounts:", re.findall(r"Rs\.?\s?[\d,]+", text))
print("dates  :", re.findall(r"\b\d{1,2}/\d{1,2}/\d{4}\b", text))
```

```output
emails : ['priya@example.com']
phones : ['98765 43210']
amounts: ['Rs. 12,500']
dates  : ['14/03/2026']
```

| Approach | Use when |
| --- | --- |
| **regular expressions** | the pattern is fixed (emails, phone numbers, ids, dates in one format) |
| **a pretrained NER model** (spaCy, Hugging Face) | names, organisations and places in free text |
| **a fine-tuned model** | your own entity types (product codes, medical terms) |
| **an LLM prompt** | quick extraction into JSON, then validate the result |

:::warning
Extracted data can be wrong. Validate it (does the date exist? does the amount match the invoice?) before using it for anything important, and treat personal details (names, phone numbers) as private data.
:::

:::interview
**Interviewers often ask:** "Why is Naive Bayes popular for text?" It is fast, needs little data, handles thousands of word features, and gives a strong baseline despite its simple assumption that words are independent.
:::
