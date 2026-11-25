---
title: Naive Bayes
summary: Classify with simple probabilities and Bayes' rule, see why the "naive" shortcut works well for text, and build a spam filter.
takeaways:
- Naive Bayes uses Bayes' rule to turn "how likely is this word in spam?" into "how likely is this message spam?"
- It is "naive" because it treats the features as independent
- It is very fast and a strong first model for text
---
## Bayes' rule in one line

From the Mathematics course: `P(class | message) is proportional to P(message | class) × P(class)`.

In plain words: **how common is spam overall, times how likely these words are in spam.** Do the same for non-spam, and pick the larger.

## Why "naive"?

To score a message, we would need the probability of the **exact combination** of words, which we will never have enough data for. The naive shortcut: **assume each word is independent** and multiply the individual word probabilities. The assumption is false ("free" and "money" often appear together), but the **ranking** of spam against not-spam usually still comes out right.

## A spam filter

```python
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
import numpy as np

messages = [
    ("win a free prize now", 1), ("claim your free money today", 1), ("urgent offer click this link", 1), ("you won a lottery claim now", 1),
    ("cheap loans approved instantly", 1), ("free gift card limited offer", 1), ("get rich quick click here", 1), ("exclusive deal win cash prize", 1),
    ("are we meeting for lunch", 0), ("please send the report by evening", 0), ("the class starts at nine tomorrow", 0), ("call me when you reach home", 0),
    ("can you share the notes from today", 0), ("happy birthday have a great day", 0), ("project meeting moved to friday", 0), ("thanks for your help yesterday", 0),
]
texts = [m for m, _ in messages]
labels = [l for _, l in messages]

model = make_pipeline(CountVectorizer(), MultinomialNB(alpha=1.0))
model.fit(texts, labels)

tests = ["claim your free prize now", "are you coming to the meeting", "win free cash click here", "send me the notes please"]
for text, p in zip(tests, model.predict_proba(tests)[:, 1]):
    print(f"spam probability {p:.2f}  <-  {text}")
```

```output
spam probability 0.99  <-  claim your free prize now
spam probability 0.02  <-  are you coming to the meeting
spam probability 0.99  <-  win free cash click here
spam probability 0.02  <-  send me the notes please
```

The filter gives high spam probabilities to messages full of "free", "win", "claim" and "click", and low ones to normal conversation.

## Which words matter most?

```python
vectorizer = model.named_steps["countvectorizer"]
classifier = model.named_steps["multinomialnb"]
words = np.array(vectorizer.get_feature_names_out())
spamminess = classifier.feature_log_prob_[1] - classifier.feature_log_prob_[0]      # how much more likely in spam
order = np.argsort(spamminess)
print("most spam-like words    :", list(words[order[-6:]][::-1]))
print("most ham-like words     :", list(words[order[:6]]))
```

```output
most spam-like words    : ['free', 'win', 'offer', 'click', 'claim', 'prize']
most ham-like words     : ['the', 'for', 'meeting', 'are', 'can', 'call']
```

Naive Bayes is easy to inspect: each word simply has a "spamminess" score.

## Smoothing: the `alpha` setting

If a word never appeared in spam training messages, its probability would be zero and wipe out the whole product. **Smoothing** (`alpha=1`) adds a tiny count to every word so nothing is exactly zero.

## Flavours

| Type | Features | Use |
| --- | --- | --- |
| **MultinomialNB** | word counts | text classification |
| **BernoulliNB** | word present or not | short messages |
| **GaussianNB** | numbers (assumed bell-shaped) | simple numeric tables |

```python
from sklearn.datasets import load_iris
from sklearn.model_selection import cross_val_score
from sklearn.naive_bayes import GaussianNB

X, y = load_iris(return_X_y=True)
print("GaussianNB on the iris flowers:", round(cross_val_score(GaussianNB(), X, y, cv=5).mean(), 3))
```

```output
GaussianNB on the iris flowers: 0.953
```

## Strengths and limits

| Strengths | Limits |
| --- | --- |
| extremely fast to train and predict | the independence assumption is wrong for correlated features |
| works with very little data | its probabilities are often over-confident |
| great baseline for text | usually beaten by stronger models when you have lots of data |

:::interview
**Interviewers often ask:** "Why is it called naive?" Because it assumes all features are independent given the class. That is rarely true, but the model still ranks the classes well, which is why it works so well for text.
:::
