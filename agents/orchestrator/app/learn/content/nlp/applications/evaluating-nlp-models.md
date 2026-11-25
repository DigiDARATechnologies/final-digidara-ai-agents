---
title: Evaluating NLP models
summary: Go beyond accuracy: precision, recall, F1, confusion matrices and language-specific metrics like BLEU and perplexity.
takeaways:
- Accuracy misleads when classes are unbalanced
- Precision, recall and F1 describe different kinds of mistakes
- Always inspect real errors, not just a single score
---
## Why accuracy is not enough

A spam filter on 1,000 emails where only 20 are spam: a model that says "not spam" for everything is **98 percent accurate** and completely useless. We need metrics that look at the **rare class**.

## Precision, recall, F1

For the class you care about (spam):

| Term | Meaning |
| --- | --- |
| **Precision** | of the emails I called spam, how many really were? (avoids false alarms) |
| **Recall** | of all real spam, how much did I catch? (avoids misses) |
| **F1** | one number balancing precision and recall |

:::formula
`precision = TP / (TP + FP)`  `recall = TP / (TP + FN)`  `F1 = 2 x precision x recall / (precision + recall)`
:::

```python
from sklearn.metrics import classification_report, confusion_matrix

actual    = ["spam", "ham", "ham", "spam", "ham", "ham", "spam", "ham", "ham", "ham"]
predicted = ["spam", "ham", "spam", "ham", "ham", "ham", "spam", "ham", "ham", "ham"]

print(confusion_matrix(actual, predicted, labels=["spam", "ham"]))
print(classification_report(actual, predicted, digits=2))
```

```output
[[2 1]
 [1 6]]
              precision    recall  f1-score   support

         ham       0.86      0.86      0.86         7
        spam       0.67      0.67      0.67         3

    accuracy                           0.80        10
   macro avg       0.76      0.76      0.76        10
weighted avg       0.80      0.80      0.80        10
```

Reading it: 2 spam were caught, 1 spam was missed (a **false negative**), and 1 good email was wrongly flagged (a **false positive**). Which mistake is worse depends on the product: for spam, losing a real email (false positive) may be worse; for a fraud alert, a missed fraud (false negative) is worse.

## Averaging for many classes

| Average | Meaning |
| --- | --- |
| **macro** | average of each class's score; every class counts equally |
| **weighted** | average weighted by class size |
| **micro** | pools all predictions (same as accuracy for single-label) |

Use **macro F1** when small classes matter.

## Metrics for other tasks

| Task | Metric | Idea |
| --- | --- | --- |
| Translation | **BLEU** | overlap of word sequences with a reference |
| Summarisation | **ROUGE** | overlap with a human summary |
| Language model | **Perplexity** | how surprised the model is by real text (lower is better) |
| NER | entity-level **F1** | whole entities must match exactly |
| Search | **precision@k**, **MRR** | are the right documents near the top? |
| Generation | human rating, LLM judge | overlap metrics miss quality |

## Good evaluation habits

1. Split data into **train, validation and test**; never tune on the test set.
2. Keep the **class balance** in splits (`stratify`).
3. Read **error examples**: which messages does it get wrong, and why? Often the fix is better data, not a bigger model.
4. Compare with a **baseline** (majority class, TF-IDF model).
5. Test on **realistic** text: typos, slang, mixed languages.

:::warning
Do not report accuracy alone on unbalanced data. Always show precision, recall and F1 for each class.
:::
