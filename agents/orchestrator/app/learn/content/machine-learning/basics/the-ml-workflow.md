---
title: The machine learning workflow
summary: The steps every project follows, shown with a first model: load data, split, train, predict and score.
takeaways:
- Always keep some data aside to test the model on
- fit() trains, predict() makes predictions, score() measures them
- A model is judged on data it has never seen
---
## Seven steps

1. **Define** the question and what you want to predict.
2. **Collect** the data.
3. **Prepare** it: clean, convert and scale.
4. **Split** it into training and test sets.
5. **Train** a model on the training set.
6. **Evaluate** it on the test set.
7. **Use** it on new data.

## A first model in a few lines

scikit-learn ships with small practice datasets. The **iris** data has measurements of 150 flowers of 3 species.

```py
pip install scikit-learn
```

```python
from sklearn.datasets import load_iris

iris = load_iris()
X, y = iris.data, iris.target          # X: features, y: the label
print(X.shape, y.shape)
print(iris.feature_names)
print(iris.target_names)
```

```output
(150, 4) (150,)
['sepal length (cm)', 'sepal width (cm)', 'petal length (cm)', 'petal width (cm)']
['setosa' 'versicolor' 'virginica']
```

By convention `X` (capital) holds the features, a table of 150 rows by 4 columns, and `y` (small) holds the answers.

## Never grade a model on the data it learned from

If a student sees the exam questions in advance, a perfect score proves nothing. A model is the same. So keep part of the data **hidden** and test on that:

```python
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
print(len(X_train), len(X_test))
```

```output
120 30
```

`test_size=0.2` keeps 20% for testing. `random_state=42` makes the shuffle repeatable, so you get the same split every time.

## Train, predict, score

```python
from sklearn.neighbors import KNeighborsClassifier

model = KNeighborsClassifier(n_neighbors=3)
model.fit(X_train, y_train)               # learn from the training data

print(model.predict(X_test[:5]))          # predictions for 5 unseen flowers
print(y_test[:5])                         # the real answers
print(model.score(X_test, y_test))        # accuracy on all test flowers
```

```output
[1 0 2 1 1]
[1 0 2 1 1]
1.0
```

Every scikit-learn model works the same way: **`fit`** to learn, **`predict`** to guess, **`score`** to measure. Once you know the pattern, you can swap one model for another by changing a single line.

:::remember
The score that matters is the one on the **test** set. A model that does very well on its training data and badly on new data has memorised, not learned. This is called overfitting, and it is the central danger in machine learning.
:::

:::note
Your numbers can differ slightly from these if your scikit-learn version is different, but the idea is the same.
:::
