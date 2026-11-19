---
title: Logistic regression and classification
summary: Predict a category with logistic regression, and see probabilities, not just labels.
takeaways:
- Despite the name, logistic regression is a classification method
- predict gives the class; predict_proba gives the probability of each class
- Scale the features first for best results
---
## From numbers to categories

**Classification** predicts a category. The simplest and most used model is **logistic regression**. Despite its name, it is for classification: it calculates the **probability** of each class, then picks the likelier one.

The **breast cancer** dataset in scikit-learn has 30 measurements for each of 569 tumours, labelled malignant (0) or benign (1):

```python
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split

data = load_breast_cancer()
X, y = data.data, data.target
print(X.shape, list(data.target_names))

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
print(len(X_train), len(X_test))
```

```output
(569, 30) ['malignant', 'benign']
455 114
```

`stratify=y` keeps the same share of each class in the training and test sets, which matters when one class is rarer.

## Train and score

```python
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
model.fit(X_train, y_train)

print("train accuracy:", round(model.score(X_train, y_train), 3))
print("test accuracy:", round(model.score(X_test, y_test), 3))
```

```output
train accuracy: 0.989
test accuracy: 0.982
```

The `make_pipeline` line scales the data and then fits the model as one unit (more in the Pipelines lesson).

## Labels and probabilities

```python
print(model.predict(X_test[:5]))
print(model.predict_proba(X_test[:3]).round(3))
```

```output
[0 1 0 1 0]
[[1.    0.   ]
 [0.    1.   ]
 [0.994 0.006]]
```

Each row of `predict_proba` is the probability of **[malignant, benign]**, and the two numbers add up to 1. `predict` simply picks the larger one.

## Changing the decision threshold

By default, a class is chosen if its probability is above 0.5. For a medical test you may not want to miss a malignant tumour, so you can accept more false alarms:

```python
proba_malignant = model.predict_proba(X_test)[:, 0]
flagged_default = (proba_malignant > 0.5).sum()
flagged_careful = (proba_malignant > 0.2).sum()
print(flagged_default, flagged_careful)
```

```output
42 47
```

A lower threshold flags more cases as malignant. Which threshold is right depends on the cost of each kind of mistake, which the next lessons cover.

:::warning
Do not judge a classifier on accuracy alone. If 95% of emails are not spam, a model that always says "not spam" is 95% accurate and completely useless. See the lesson on evaluating classifiers.
:::

:::interview
**Interviewers often ask:** "Is logistic regression a regression or a classification algorithm?" Classification. It uses a straight-line formula, then the **sigmoid** function squeezes the result into a probability between 0 and 1.
:::
