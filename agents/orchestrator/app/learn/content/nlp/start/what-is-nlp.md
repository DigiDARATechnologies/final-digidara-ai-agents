---
title: What is NLP? Tasks and the pipeline
summary: See what natural language processing can do, the main tasks, and the steps of a typical NLP project.
takeaways:
- NLP teaches computers to work with human language
- Most tasks are classification, tagging, generation or search
- Every project follows: collect, clean, represent, model, evaluate
---
## What NLP is

**Natural Language Processing (NLP)** is the part of AI that lets computers read, understand and produce human language. Every time you use autocomplete, translate a page, filter spam or talk to a chatbot, NLP is working.

Language is hard for computers because it is **ambiguous**: "I saw her duck" (a bird, or she lowered her head?), "bank" (river or money?), and the same idea has many wordings.

## The main tasks

| Task | Input to output | Example |
| --- | --- | --- |
| **Text classification** | text to a label | spam or not spam, news category |
| **Sentiment analysis** | text to positive, negative, neutral | product review |
| **Named entity recognition (NER)** | text to names, dates, places | "Meet Asha in Chennai on Monday" |
| **Part-of-speech tagging** | words to noun, verb, ... | grammar tools |
| **Machine translation** | language A to language B | English to Hindi |
| **Summarisation** | long text to short text | news digest |
| **Question answering** | question (and text) to an answer | search, chatbots |
| **Text generation** | prompt to new text | LLMs |
| **Search and similarity** | query to the most relevant texts | semantic search |
| **Speech to text** | audio to text | voice assistants |

## The typical pipeline

```text
1. Collect text      (reviews, tickets, documents)
2. Clean             (lowercase, remove noise, handle spelling)
3. Tokenise          (split into words or sub-words)
4. Represent         (counts, TF-IDF, embeddings)
5. Model             (Naive Bayes, logistic regression, neural network, LLM)
6. Evaluate          (precision, recall, F1)
7. Deploy and monitor
```

## Three eras of NLP

| Era | Approach | Example |
| --- | --- | --- |
| **Rules** | hand-written patterns | "if the text contains 'refund' then billing" |
| **Statistics and classic ML** | counts plus Naive Bayes, SVM | TF-IDF classifiers (this course's start) |
| **Deep learning** | embeddings, RNNs, **transformers** | BERT, GPT, modern LLMs |

Today large pre-trained transformers solve most tasks, but classic methods are still fast, cheap and easy to explain, so they remain the right choice for many small problems.

## Which approach to choose

1. Start with a **simple baseline** (TF-IDF plus logistic regression). It is often good enough.
2. If accuracy is not enough, try a **pre-trained transformer** (BERT) fine-tuned on your data.
3. For open-ended generation or reasoning, use an **LLM** (Generative AI course).

:::tip
Always build the simple baseline first. If a fancy model is only 1 percent better, the baseline is easier to run, explain and maintain.
:::
