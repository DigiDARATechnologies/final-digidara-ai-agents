---
title: Decision trees
summary: A tree asks a series of yes or no questions; learn how it works, why it overfits and how depth controls that.
takeaways:
- A decision tree splits the data with simple questions
- A tree that grows too deep memorises the training data
- max_depth limits the size and reduces overfitting
---
## Twenty questions

A **decision tree** predicts by asking questions about the features, one at a time: "Is the petal length below 2.5? If yes, it is species A; if not, ask the next question." It is easy to read, which makes it popular.

```python
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier, export_text

iris = load_iris()
X_train, X_test, y_train, y_test = train_test_split(iris.data, iris.target, test_size=0.3, random_state=0)

tree = DecisionTreeClassifier(max_depth=2, random_state=0)
tree.fit(X_train, y_train)
print("test accuracy:", round(tree.score(X_test, y_test), 3))
print(export_text(tree, feature_names=iris.feature_names))
```

```output
test accuracy: 0.911
|--- petal width (cm) <= 0.75
|   |--- class: 0
|--- petal width (cm) >  0.75
|   |--- petal length (cm) <= 4.95
|   |   |--- class: 1
|   |--- petal length (cm) >  4.95
|   |   |--- class: 2
```

You can read the rules straight from the output: this tree first checks one measurement, then a second question inside each branch.

## Which features mattered?

```python
for name, importance in zip(iris.feature_names, tree.feature_importances_):
    print(f"{name:20s} {importance:.2f}")
```

```output
sepal length (cm)    0.00
sepal width (cm)     0.00
petal length (cm)    0.44
petal width (cm)     0.56
```

## Trees can memorise

A tree with no limit keeps splitting until every training row is classified perfectly. That can be too perfect:

```python
for depth in [1, 2, 3, 5, None]:
    t = DecisionTreeClassifier(max_depth=depth, random_state=0).fit(X_train, y_train)
    print(f"depth={str(depth):4s} train={t.score(X_train, y_train):.3f} test={t.score(X_test, y_test):.3f}")
```

```output
depth=1    train=0.695 test=0.600
depth=2    train=0.962 test=0.911
depth=3    train=0.981 test=0.978
depth=5    train=1.000 test=0.978
depth=None train=1.000 test=0.978
```

From depth 3 onward the **training** score climbs to 1.000, but the **test** score does not improve: the extra depth adds complexity and no accuracy. When the training score keeps rising and the test score does not, the tree is starting to memorise. This is **overfitting**. On this small, easy dataset the damage is tiny; the cross-validation lesson shows a clearer case.

| Setting | Effect |
| --- | --- |
| `max_depth` | the most questions in a row |
| `min_samples_split` | needs at least this many rows to split further |
| `min_samples_leaf` | each final group must have at least this many rows |

## Strengths and weaknesses

| Strengths | Weaknesses |
| --- | --- |
| easy to explain and draw | overfits unless you limit it |
| no scaling needed | a small change in data can change the whole tree |
| handles numbers and categories | usually less accurate than an ensemble of trees |

:::interview
**Interviewers often ask:** "How does a decision tree decide where to split?" It tries each feature and threshold and picks the split that makes the groups **purest**, measured by Gini impurity or entropy.
:::
