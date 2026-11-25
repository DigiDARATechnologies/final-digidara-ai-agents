---
title: NLP interview questions
summary: Common NLP questions with short answers, from preprocessing and TF-IDF to transformers and evaluation.
takeaways:
- Be ready to explain preprocessing, TF-IDF, embeddings and attention
- Know precision, recall and F1, and when accuracy misleads
- Give a small example with each answer
kind: qa
---
### Q [Easy] What is NLP? Give examples.
The field of AI that enables computers to understand and produce human language. Examples: spam filtering, translation, sentiment analysis, chatbots and search.

### Q [Easy] What is tokenization?
Splitting text into smaller units (words, sub-words or characters) that a model can process.

### Q [Easy] Stemming vs lemmatization?
Stemming chops word endings by rule ("studies" to "studi"); lemmatization uses a dictionary to return the real base word ("studies" to "study"). Lemmatization is more accurate but slower.

### Q [Easy] What are stop words and should you always remove them?
Very common words such as "the" and "is". Removing them helps with counting methods, but not always: "not" changes meaning, and transformers need full sentences.

### Q [Medium] Explain bag of words and its drawbacks.
Represents text by word counts, ignoring order. It is simple but loses word order and meaning, and vectors are large and sparse.

### Q [Medium] What is TF-IDF?
Term frequency times inverse document frequency. It gives high weight to words frequent in a document but rare across all documents, so common words get little weight.

### Q [Medium] What are word embeddings and why are they better than one-hot vectors?
Dense vectors where similar words are close together (Word2Vec, GloVe). They capture meaning and are small, whereas one-hot vectors are huge and treat all words as equally different.

### Q [Medium] What is cosine similarity?
The cosine of the angle between two vectors, from 0 (unrelated) to 1 (same direction). It compares direction rather than length, so it works for documents of different sizes.

### Q [Medium] Why is accuracy a poor metric for unbalanced data? What do you use instead?
A model predicting the majority class can score high accuracy yet be useless. Use precision, recall, F1 (macro for many classes) and the confusion matrix.

### Q [Medium] What is named entity recognition?
Finding and labelling entities such as people, places, organisations, dates and amounts in text.

### Q [Medium] How does Naive Bayes work for text and why "naive"?
It uses Bayes' theorem to compute the probability of each class given the words, assuming words are independent given the class. The assumption is unrealistic, but it works well and is fast.

### Q [Hard] What problem do RNNs have, and how do LSTMs help?
Vanishing gradients make simple RNNs forget long-range context. LSTMs add gates to keep or forget information, preserving it over longer sequences.

### Q [Hard] What is attention and why did transformers replace RNNs?
Attention lets each token weigh every other token when building its representation. Transformers process all tokens in parallel (fast to train) and handle long-range context better than RNNs.

### Q [Hard] BERT vs GPT?
BERT is an encoder that reads both directions and is suited to understanding tasks (classification, NER, QA). GPT is a decoder that predicts the next token left to right and is suited to generation.

### Q [Hard] What is transfer learning in NLP?
Reusing a model pre-trained on huge text and fine-tuning it on a small labelled dataset for your task, which needs far less data and compute than training from scratch.

### Q [Hard] How would you build a text classifier for a new problem?
Collect and label data, split into train and test, build a TF-IDF plus logistic regression baseline, evaluate with F1, inspect errors, then try a fine-tuned transformer if needed, and monitor in production.

### Q [Hard] What is BLEU and what are its limits?
A metric comparing the word sequences of a translation to reference translations. It ignores meaning, so good paraphrases can score low; use it with human review.
