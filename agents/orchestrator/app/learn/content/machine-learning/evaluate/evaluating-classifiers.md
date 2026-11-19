---
title: Evaluating classifiers
summary: Look beyond accuracy: the confusion matrix, precision, recall and F1.
takeaways:
- Accuracy hides problems when the classes are unbalanced
- The confusion matrix shows exactly which mistakes the model makes
- Precision asks "when it says yes, is it right?"; recall asks "did it find them all?"
---
## Why accuracy is not enough

Imagine 1,000 patients, and only 20 have a disease. A "model" that says **everyone is healthy** is 98% accurate and catches none of the sick patients. We need better measures.

## The confusion matrix

It counts every combination of the real answer and the prediction:

```python
from sklearn.datasets import load_breast_cancer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

data = load_breast_cancer()
X_train, X_test, y_train, y_test = train_test_split(data.data, data.target, test_size=0.3, random_state=7, stratify=data.target)
model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(X_train, y_train)
pred = model.predict(X_test)

print(confusion_matrix(y_test, pred))
```

```output
[[ 63   1]
 [  3 104]]
```

Rows are the **real** class and columns are the **predicted** class. In this data 0 means malignant and 1 means benign:

| | Predicted malignant | Predicted benign |
| --- | --- | --- |
| **Really malignant** | 63 | 1 |
| **Really benign** | 3 | 104 |

Pick one class as the **positive** one. Taking **benign** as positive, the four counts have names:

| Name | Meaning | Here |
| --- | --- | --- |
| True positive (TP) | said yes, and it was yes | 104 benign called benign |
| True negative (TN) | said no, and it was no | 63 malignant called malignant |
| False positive (FP) | said yes, but it was no (a false alarm) | 1 malignant called benign |
| False negative (FN) | said no, but it was yes (a miss) | 3 benign called malignant |

Notice that the two kinds of mistake are not equally serious. Calling a malignant tumour benign (the 1 false positive here) is far more dangerous than the reverse. This is why accuracy alone is not enough.

## Precision, recall and F1

:::formula
Precision = TP / (TP + FP)

Recall = TP / (TP + FN)

F1 = 2 × Precision × Recall / (Precision + Recall)
:::

| Measure | Question it answers | Care about it when |
| --- | --- | --- |
| **Precision** | when the model says yes, how often is it right? | false alarms are costly (flagging a good email as spam) |
| **Recall** | of all the real yes cases, how many did it find? | misses are costly (missing a disease) |
| **F1** | a balance of the two | you need both |

```python
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

print("accuracy :", round(accuracy_score(y_test, pred), 3))
print("precision:", round(precision_score(y_test, pred), 3))
print("recall   :", round(recall_score(y_test, pred), 3))
print("f1       :", round(f1_score(y_test, pred), 3))
```

```output
accuracy : 0.977
precision: 0.99
recall   : 0.972
f1       : 0.981
```

## The full report

```python
from sklearn.metrics import classification_report

print(classification_report(y_test, pred, target_names=data.target_names))
```

```output
              precision    recall  f1-score   support

   malignant       0.95      0.98      0.97        64
      benign       0.99      0.97      0.98       107

    accuracy                           0.98       171
   macro avg       0.97      0.98      0.98       171
weighted avg       0.98      0.98      0.98       171
```

Here "support" is the number of real examples of each class in the test set.

## A trade-off

Precision and recall pull in opposite directions. If you make the model more cautious (so it flags more cases), recall goes up and precision usually goes down. Choose the balance by asking: **which mistake costs more?**

:::remember
For regression there is no confusion matrix. Use MAE, RMSE and R² (see the linear regression lesson).
:::

:::interview
**Interviewers often ask:** "Your dataset has 95% of one class. How do you evaluate a model?" Do not use accuracy alone. Use precision, recall, F1 and the confusion matrix, and consider stratified splits and class weights.
:::
