---
title: Text preprocessing
summary: Turn messy human text into clean tokens: lowercasing, tokenisation, stop words, stemming and lemmatisation.
takeaways:
- Computers need text cleaned and split into tokens before they can use it
- Stop-word removal and stemming shrink the vocabulary; lemmatisation does it more carefully
- Preprocessing choices change the results, so apply the same steps to training and new text
---
## What NLP is

**Natural Language Processing (NLP)** teaches computers to work with human language: reading reviews, answering questions, translating, summarising. Computers only understand numbers, so the first job is always the same: **clean the text and turn it into tokens, then into numbers.**

| Task | Example |
| --- | --- |
| classification | spam or not spam; positive or negative review |
| information extraction | find names, dates and amounts in a document |
| search and retrieval | match a question to the best FAQ answer |
| generation and translation | chatbots, summaries, language translation |

## Step 1: clean and lowercase

```python
import re

review = "  The Delivery was LATE!!! I waited 3 days... but the product is GOOD :) "

text = review.lower().strip()
text = re.sub(r"[^a-z0-9\s]", " ", text)          # keep letters, digits and spaces
text = re.sub(r"\s+", " ", text).strip()
print(text)
```

```output
the delivery was late i waited 3 days but the product is good
```

## Step 2: tokenisation

**Tokenisation** splits text into pieces (usually words), called **tokens**.

```python
tokens = text.split()
print(tokens)
print("number of tokens:", len(tokens))
```

```output
['the', 'delivery', 'was', 'late', 'i', 'waited', '3', 'days', 'but', 'the', 'product', 'is', 'good']
number of tokens: 13
```

Splitting on spaces works for simple English. Real text needs care: "don't", "New York", hashtags, and languages without spaces. Libraries such as NLTK and spaCy tokenise properly. Modern transformer models use **subword** tokens that split rare words into pieces.

## Step 3: stop words

**Stop words** are very common words (the, is, a, of) that add little meaning for many tasks.

```python
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

filtered = [t for t in tokens if t not in ENGLISH_STOP_WORDS]
print(filtered)
print("removed:", [t for t in tokens if t in ENGLISH_STOP_WORDS])
```

```output
['delivery', 'late', 'waited', '3', 'days', 'product', 'good']
removed: ['the', 'was', 'i', 'but', 'the', 'is']
```

Removing them makes the text shorter. But be careful: for **sentiment**, words like "not" matter ("not good"). Check what is on your stop-word list, and remove "not" and "no" from it when meaning depends on them.

```python
print("'not' is a stop word:", "not" in ENGLISH_STOP_WORDS)
print("'good' is a stop word:", "good" in ENGLISH_STOP_WORDS)
```

```output
'not' is a stop word: True
'good' is a stop word: False
```

## Step 4: stemming

**Stemming** chops word endings to get a rough root, so that "running", "runs" and "run" count as one word. It is fast but crude.

```python
from nltk.stem import PorterStemmer

stemmer = PorterStemmer()
for word in ["running", "runs", "studies", "studying", "better", "delivered", "delivery"]:
    print(f"{word:<10} -> {stemmer.stem(word)}")
```

```output
running    -> run
runs       -> run
studies    -> studi
studying   -> studi
better     -> better
delivered  -> deliv
delivery   -> deliveri
```

Stems are not always real words (`studies` becomes `studi`), and words with different meanings can collide. That is acceptable when the goal is only to group similar words.

## Step 5: lemmatisation

**Lemmatisation** uses a dictionary and grammar to return the real base word: "better" becomes "good", "studies" becomes "study". It is slower but more accurate.

```py
import nltk
nltk.download("wordnet")                      # one-time download of the dictionary
from nltk.stem import WordNetLemmatizer

lemmatizer = WordNetLemmatizer()
print(lemmatizer.lemmatize("studies"))               # study
print(lemmatizer.lemmatize("better", pos="a"))       # good  (a = adjective)
print(lemmatizer.lemmatize("running", pos="v"))      # run   (v = verb)
```

| | Stemming | Lemmatisation |
| --- | --- | --- |
| Method | cut off endings by rules | dictionary and grammar |
| Output | may not be a real word | a real word |
| Speed | very fast | slower |
| Use when | speed matters, rough grouping is enough | meaning matters |

## A preprocessing function

Wrap the steps in one function and use it everywhere, **the same way on training data and on new text**:

```python
KEEP = {"not", "no", "never"}                              # words that carry meaning for sentiment

def preprocess(text):
    text = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    words = [w for w in text.split() if w not in (ENGLISH_STOP_WORDS - KEEP)]
    return [stemmer.stem(w) for w in words]

print(preprocess("The delivery was NOT on time, but the packing was great!"))
print(preprocess("Delivered quickly and the product works perfectly."))
```

```output
['deliveri', 'not', 'time', 'pack', 'great']
['deliv', 'quickli', 'product', 'work', 'perfectli']
```

Notice that "not" survived. Notice also how crude stemming is: "delivered" became `deliv` but "delivery" became `deliveri`, so the model still sees them as two different words. A lemmatiser would map both to "deliver". Stemming is fast and rough, and it does not always group what you expect.

:::warning
More cleaning is not always better. Modern transformer models usually work best on **lightly cleaned** text, because they learn from the whole sentence, punctuation and word endings included. Heavy preprocessing is mainly for classic methods such as Bag of Words and TF-IDF.
:::
