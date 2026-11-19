---
title: Linear regression
summary: Predict a number by fitting a straight line, and read the slope, the intercept and the R² score.
takeaways:
- Linear regression fits y = slope × x + intercept
- coef_ and intercept_ are what the model learned
- R², MAE and RMSE tell you how well it fits
---
## Fitting a line

Does studying more give better marks? Here are ten students:

```python
import numpy as np
from sklearn.linear_model import LinearRegression

hours = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]).reshape(-1, 1)    # a column: one feature
marks = np.array([35, 42, 50, 54, 62, 65, 74, 78, 85, 90])

model = LinearRegression()
model.fit(hours, marks)

print("slope:", round(model.coef_[0], 2))
print("intercept:", round(model.intercept_, 2))
```

```output
slope: 6.05
intercept: 30.2
```

`reshape(-1, 1)` turns the list into a column, because scikit-learn expects features as a table (rows by columns).

The model learned: **marks ≈ 6.05 × hours + 30.2**. Each extra hour of study adds about 6 marks, and a student who studies 0 hours would get about 30.

## Predicting

```python
print(model.predict([[5.5], [12]]).round(1))
```

```output
[ 63.5 102.9]
```

Be careful with the 12 hours: it is **outside** the range the model saw (1 to 10). The line says about 103 marks, which is impossible on a 100-mark paper. A straight line keeps going, but real life does not. Predictions outside the training range are guesses.

## How good is the fit?

```python
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

pred = model.predict(hours)
print("R2:", round(r2_score(marks, pred), 3))
print("MAE:", round(mean_absolute_error(marks, pred), 2))
print("RMSE:", round(mean_squared_error(marks, pred) ** 0.5, 2))
```

```output
R2: 0.996
MAE: 0.98
RMSE: 1.11
```

| Metric | Meaning |
| --- | --- |
| **MAE** | the average size of the error, in the units of the answer (marks) |
| **RMSE** | like MAE but punishes large errors more |
| **R²** | the share of the variation the model explains: 1 is perfect, 0 is no better than guessing the average |

## More than one feature

Real problems have many features. The code is the same:

```python
from sklearn.model_selection import train_test_split

# hours studied, hours slept, attendance %
X = np.array([[2, 6, 60], [4, 7, 70], [6, 6, 80], [8, 8, 85], [3, 5, 55],
              [7, 7, 90], [5, 8, 75], [9, 6, 95], [1, 5, 50], [10, 7, 92]])
y = np.array([40, 55, 66, 80, 44, 82, 65, 90, 33, 94])

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=0)
multi = LinearRegression().fit(X_train, y_train)
print("coefficients:", multi.coef_.round(2))
print("R2 on test:", round(multi.score(X_test, y_test), 3))
```

```output
coefficients: [3.17 1.14 0.82]
R2 on test: 0.861
```

There is one coefficient per feature. A bigger coefficient means that feature moves the prediction more (when the features are on a similar scale).

:::remember
Linear regression assumes the relationship is a straight line. Plot your data first. If it is a curve, a straight line will be wrong however you tune it.
:::

:::interview
**Interviewers often ask:** "What does R² tell you?" The proportion of the variance in the target that the model explains. 0.9 means the model explains about 90% of the variation. Add that a high R² on **training** data alone does not mean the model is good.
:::
