---
title: Sentiment analysis
summary: Build a classifier that tells whether a review is positive or negative, using TF-IDF and logistic regression, and learn what it gets wrong.
takeaways:
- Sentiment analysis is text classification: TF-IDF turns text into numbers and a classifier learns from labelled examples
- The model's coefficients show which words push towards positive or negative
- Negation, sarcasm and unseen words are the classic weaknesses
---
## The task

Given a review such as "The battery life is excellent", decide **positive** or **negative**. Companies use it to read thousands of reviews and tweets at once.

## Labelled data

We build a small practice set from templates. (Real projects use datasets such as product reviews or movie reviews; the method is identical.)

```python
import random
random.seed(0)

positive_parts = ["excellent", "great", "amazing", "very good", "love it", "works perfectly", "fast delivery", "worth the money", "highly recommended", "superb quality"]
negative_parts = ["terrible", "very bad", "waste of money", "stopped working", "late delivery", "poor quality", "not good", "disappointed", "broke in a week", "would not recommend"]
subjects = ["the phone", "this laptop", "the headphones", "the service", "this product", "the shoes", "the delivery", "the camera"]

reviews, labels = [], []
for _ in range(120):
    reviews.append(f"{random.choice(subjects)} is {random.choice(positive_parts)}")
    labels.append(1)
    reviews.append(f"{random.choice(subjects)} is {random.choice(negative_parts)}")
    labels.append(0)

print(len(reviews), "reviews, positive share:", sum(labels) / len(labels))
print(reviews[0], "->", labels[0])
print(reviews[1], "->", labels[1])
```

```output
240 reviews, positive share: 0.5
the delivery is fast delivery -> 1
the phone is late delivery -> 0
```

## Train and test

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline

X_train, X_test, y_train, y_test = train_test_split(reviews, labels, test_size=0.25, random_state=0, stratify=labels)

model = make_pipeline(TfidfVectorizer(ngram_range=(1, 2)), LogisticRegression(max_iter=1000))
model.fit(X_train, y_train)

print("test accuracy:", round(accuracy_score(y_test, model.predict(X_test)), 3))
```

```output
test accuracy: 1.0
```

The accuracy is near perfect, but be careful: our data was generated from a small set of phrases, so this is **easy**. Real reviews are much messier and a good score might be 85 to 92%.

## What did the model learn?

The coefficients show which words push towards positive or negative:

```python
import numpy as np

vectorizer = model.named_steps["tfidfvectorizer"]
classifier = model.named_steps["logisticregression"]
words = np.array(vectorizer.get_feature_names_out())
order = np.argsort(classifier.coef_[0])

print("most negative:", list(words[order[:6]]))
print("most positive:", list(words[order[-6:]]))
```

```output
most negative: ['disappointed', 'is disappointed', 'is terrible', 'terrible', 'not', 'late']
most positive: ['great', 'is great', 'is amazing', 'amazing', 'excellent', 'is excellent']
```

This is a big advantage of a simple model: you can read **why** it decides.

## Predict new text

```python
new = [
    "the camera is superb quality",
    "this phone is a waste of money",
    "the shoes are not good",
    "this laptop is not bad at all",
]
for text, p in zip(new, model.predict_proba(new)[:, 1]):
    print(f"{p:.2f} positive  <-  {text}")
```

```output
0.77 positive  <-  the camera is superb quality
0.25 positive  <-  this phone is a waste of money
0.29 positive  <-  the shoes are not good
0.24 positive  <-  this laptop is not bad at all
```

The first three are handled well. The last one, "not bad at all", means something positive, but the model only saw "not good" as negative, so it leans the wrong way. **Negation** is the classic weakness of word-counting models.

## Common weaknesses

| Problem | Example | Fix |
| --- | --- | --- |
| **negation** | "not bad", "not good" | bigrams (we used them), or a transformer |
| **sarcasm** | "Great, it broke on day one" | needs context; hard for any model |
| **words never seen** | new slang or product names | embeddings or transformers |
| **domain change** | movie-review model used on bank reviews | train on your own domain's data |
| **mixed opinions** | "great camera, terrible battery" | aspect-based sentiment |

## Measure properly

For real data use more than accuracy:

```python
from sklearn.metrics import classification_report
print(classification_report(y_test, model.predict(X_test), target_names=["negative", "positive"], digits=2))
```

```output
              precision    recall  f1-score   support

    negative       1.00      1.00      1.00        30
    positive       1.00      1.00      1.00        30

    accuracy                           1.00        60
   macro avg       1.00      1.00      1.00        60
weighted avg       1.00      1.00      1.00        60
```

Check **precision and recall for each class**, especially if one class is rarer than the other, and look at a sample of the **mistakes** by hand: they teach you more than the score.

## The modern shortcut

For serious work, use a pretrained transformer. It handles negation and context far better:

```py
from transformers import pipeline
classify = pipeline("sentiment-analysis")
print(classify("This laptop is not bad at all"))
```

:::interview
**Interviewers often ask:** "How would you build a sentiment classifier?" Collect and label text, clean it, convert to TF-IDF vectors, train logistic regression as a baseline, evaluate with precision and recall per class, inspect errors (negation, sarcasm), and move to a pretrained transformer if the baseline is not enough.
:::
