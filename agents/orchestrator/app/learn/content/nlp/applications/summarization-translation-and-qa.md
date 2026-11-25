---
title: Summarization, translation and question answering
summary: Understand extractive versus abstractive summaries, how machine translation works, and the two styles of question answering.
takeaways:
- Extractive summaries pick existing sentences; abstractive summaries write new ones
- Modern translation and abstractive summaries use transformer models
- Question answering is either extractive (find the span) or generative (write the answer)
---
## Summarisation

**Extractive**: choose the most important **existing sentences**. Safe (no invented facts) but can read choppily.
**Abstractive**: **write new sentences** that capture the meaning, like a human. More natural, but can **hallucinate**.

A simple extractive summariser: score each sentence by how many frequent words it contains and keep the top ones.

```python
import re
from collections import Counter

text = (
    "The college announced a new placement drive this month. "
    "More than fifty companies will visit the campus for placement and hiring. "
    "Students must register on the portal before the placement deadline. "
    "The canteen will also remain open late during the drive. "
    "Companies will hire for software, data and support roles."
)

sentences = re.split(r"(?<=[.!?])\s+", text)
stop = {"the", "a", "will", "for", "and", "on", "this", "also", "more", "than", "must", "during", "before", "of", "to"}
words = [w for w in re.findall(r"[a-z]+", text.lower()) if w not in stop]
frequency = Counter(words)

def score(sentence):
    tokens = [w for w in re.findall(r"[a-z]+", sentence.lower()) if w not in stop]
    return sum(frequency[w] for w in tokens) / max(len(tokens), 1)

best = sorted(sentences, key=score, reverse=True)[:2]
summary = [s for s in sentences if s in best]      # keep original order
print(" ".join(summary))
```

```output
The college announced a new placement drive this month. More than fifty companies will visit the campus for placement and hiring.
```

Real systems score sentences with embeddings or use an abstractive model:

```python
from transformers import pipeline
summarizer = pipeline("summarization")
print(summarizer(long_article, max_length=80, min_length=30)[0]["summary_text"])
```

## Machine translation

Early systems used rules, then statistics; today **encoder-decoder transformers** translate: the encoder reads the source sentence, the decoder writes the target, attending to the source words. Quality is high for common language pairs and weaker for low-resource languages and idioms.

```python
from transformers import pipeline
translate = pipeline("translation_en_to_fr")
print(translate("Where is the railway station?")[0]["translation_text"])
```

Challenges: word order differs between languages, idioms ("break a leg"), gender and politeness, and rare languages with little training data. Indian-language models such as IndicTrans2 help here.

## Question answering

| Style | How | Good for |
| --- | --- | --- |
| **Extractive QA** | find the **span** of text that answers inside a given passage | exact facts from a document |
| **Generative QA** | an LLM writes the answer, usually with retrieved passages (RAG) | explanations, multi-part answers |
| **Retrieval + reader** | search first, then read the best passages | large document collections |

Extractive QA cannot answer if the text does not contain the answer, but it never invents one. Generative answers are more flexible but need grounding (RAG, covered in the Generative AI course) to avoid hallucination.

## Evaluating these tasks

| Task | Common metric |
| --- | --- |
| Summarisation | **ROUGE** (word overlap with a human summary) |
| Translation | **BLEU** (overlap of word groups with a reference) |
| QA | **Exact match** and **F1** on the answer span |

Overlap metrics are crude (a good paraphrase scores low), so also read samples and use human review.

:::tip
For a summariser in a product, extractive is the safer start. Move to abstractive only when you can check the output for invented facts.
:::
