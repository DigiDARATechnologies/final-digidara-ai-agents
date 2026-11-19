---
title: Cross-validation and tuning
summary: Get a steadier score with cross-validation, spot overfitting, and pick settings with grid search.
takeaways:
- One test split can be lucky or unlucky; cross-validation averages several
- A big gap between train and test scores means overfitting
- GridSearchCV tries settings and keeps the best, using cross-validation
---
## One split can mislead

A single train/test split gives one score, and a different random split gives a different one. **Cross-validation** tests the model several times and averages.

In **5-fold** cross-validation, the data is cut into 5 parts. Each part takes a turn as the test set while the other 4 train the model.

```python
from sklearn.datasets import load_breast_cancer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

data = load_breast_cancer()
X, y = data.data, data.target

model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
scores = cross_val_score(model, X, y, cv=5)
print(scores.round(3))
print("mean:", round(scores.mean(), 3), " spread:", round(scores.std(), 3))
```

```output
[0.982 0.982 0.974 0.974 0.991]
mean: 0.981  spread: 0.007
```

Report the **mean** and the **spread**. A small spread means the model is stable.

## Overfitting and underfitting

| | Train score | Test score | Meaning |
| --- | --- | --- | --- |
| **Underfitting** | low | low | the model is too simple |
| **Good fit** | high | similar | it learned the real pattern |
| **Overfitting** | very high | much lower | it memorised the training data |

```python
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=5, stratify=y)
for depth in [1, 3, 6, None]:
    t = DecisionTreeClassifier(max_depth=depth, random_state=5).fit(X_train, y_train)
    print(f"depth={str(depth):4s} train={t.score(X_train, y_train):.3f} test={t.score(X_test, y_test):.3f}")
```

```output
depth=1    train=0.920 test=0.924
depth=3    train=0.962 test=0.947
depth=6    train=0.992 test=0.953
depth=None train=1.000 test=0.942
```

With no depth limit the tree scores 1.000 on training data but less on test data. That gap is the signature of overfitting.

How to reduce it: use **more data**, a **simpler model**, **limits** such as `max_depth`, or **regularisation**.

## Choosing settings: grid search

Settings you choose yourself before training (such as `max_depth`) are **hyperparameters**. Rather than guessing, try a grid of values and keep the best by cross-validation:

```python
from sklearn.model_selection import GridSearchCV

grid = GridSearchCV(
    DecisionTreeClassifier(random_state=5),
    param_grid={"max_depth": [2, 3, 4, 5, 6], "min_samples_leaf": [1, 5, 10]},
    cv=5,
)
grid.fit(X_train, y_train)
print("best settings:", grid.best_params_)
print("best CV score:", round(grid.best_score_, 3))
print("score on the untouched test set:", round(grid.score(X_test, y_test), 3))
```

```output
best settings: {'max_depth': 3, 'min_samples_leaf': 1}
best CV score: 0.93
score on the untouched test set: 0.947
```

Notice that the **test set was not used to choose the settings**. It only gives the final, honest score.

:::warning
If you keep adjusting a model until the **test** score looks good, you have effectively trained on the test set. Choose settings with cross-validation on the training data, and look at the test set once at the end.
:::

:::interview
**Interviewers often ask:** "How do you detect and reduce overfitting?" Detect it by a large gap between training and validation scores. Reduce it with more data, a simpler model, regularisation, early stopping, dropout (for neural networks) or ensembles.
:::
