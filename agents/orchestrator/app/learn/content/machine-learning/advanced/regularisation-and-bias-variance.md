---
title: Bias, variance and regularisation
summary: Understand why models underfit and overfit, see it with real numbers, and control it with regularisation, Ridge and Lasso.
takeaways:
- Underfitting (high bias) is too simple; overfitting (high variance) memorises noise
- Test error is U-shaped as models get more complex; the best model sits at the bottom
- Regularisation adds a penalty on large weights; Ridge shrinks them, Lasso can set them to zero
---
## Two ways to be wrong

Imagine fitting a curve through noisy points.

| | Too simple | Too complex |
| --- | --- | --- |
| Name | **underfitting** (high **bias**) | **overfitting** (high **variance**) |
| What happens | misses the real pattern | learns the noise as if it were pattern |
| Training error | high | very low |
| Test error | high | high |
| Fix | a richer model, better features | more data, simpler model, regularisation |

The goal is the middle: capture the real pattern and ignore the noise.

## See it with numbers

We create noisy data from a sine curve, then fit polynomials of degree 1, 3 and 9:

```python
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

rng = np.random.default_rng(1)
x = np.sort(rng.uniform(0, 1, 30))
y = np.sin(2 * np.pi * x) + rng.normal(0, 0.25, size=30)
X = x.reshape(-1, 1)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.5, random_state=1)

for degree in (1, 3, 9):
    model = make_pipeline(PolynomialFeatures(degree, include_bias=False), StandardScaler(), LinearRegression())
    model.fit(X_train, y_train)
    train_rmse = mean_squared_error(y_train, model.predict(X_train)) ** 0.5
    test_rmse = mean_squared_error(y_test, model.predict(X_test)) ** 0.5
    print(f"degree {degree:>2}: train RMSE {train_rmse:.2f}   test RMSE {test_rmse:.2f}")
```

```output
degree  1: train RMSE 0.37   test RMSE 0.62
degree  3: train RMSE 0.19   test RMSE 0.25
degree  9: train RMSE 0.10   test RMSE 0.54
```

Read it like a doctor reading a chart:

- **Degree 1** (a straight line) is wrong on both sets: the data is a wave, and a line cannot bend. That is **underfitting**.
- **Degree 3** captures the wave and has similar, low errors on both sets.
- **Degree 9** has the lowest training error but a **much worse** test error (more than twice the degree-3 error). It twists to pass through every training point, noise included. That is **overfitting**.

The tell-tale sign of overfitting is a **big gap** between training and test error.

## The bias-variance trade-off

| Term | Meaning |
| --- | --- |
| **Bias** | error from wrong, over-simple assumptions (the model cannot reach the truth) |
| **Variance** | how much the model changes if trained on different samples of data (it follows noise) |
| **Irreducible noise** | randomness in the data that no model can remove |

Making a model more flexible lowers bias but raises variance. The best test error is a compromise, which is why test error forms a **U shape** as complexity increases.

## Regularisation: a leash on the model

**Regularisation** adds a penalty for large coefficients to the training goal. A model can still bend, but only if the improvement is worth the cost. The strength is a number `alpha` (in scikit-learn): bigger `alpha` means a stronger leash.

| Method | Penalty | Effect |
| --- | --- | --- |
| **Ridge** (L2) | sum of squared weights | shrinks all weights smoothly toward zero |
| **Lasso** (L1) | sum of absolute weights | pushes some weights **exactly to zero**, so it also selects features |
| **Elastic Net** | a mix of both | a compromise, helpful when features are correlated |

The same flexible degree-9 model, with Ridge:

```python
from sklearn.linear_model import Ridge

for alpha in (1e-4, 1e-2, 1e-1, 1, 10):
    model = make_pipeline(PolynomialFeatures(9, include_bias=False), StandardScaler(), Ridge(alpha=alpha))
    model.fit(X_train, y_train)
    test_rmse = mean_squared_error(y_test, model.predict(X_test)) ** 0.5
    print(f"alpha {alpha:>8}: test RMSE {test_rmse:.2f}")
```

```output
alpha   0.0001: test RMSE 0.74
alpha     0.01: test RMSE 0.24
alpha      0.1: test RMSE 0.29
alpha        1: test RMSE 0.50
alpha       10: test RMSE 0.72
```

With a tiny penalty the degree-9 curve still overfits. Around `alpha` 0.01 the test error reaches its lowest point, close to the degree-3 model, and as the penalty grows further the model is squeezed into underfitting and the error climbs again. That is the U shape. You choose `alpha` with **cross-validation**, using `RidgeCV` or `GridSearchCV`.

## Lasso as an automatic feature selector

```python
from sklearn.datasets import make_regression
from sklearn.linear_model import Lasso

X, y = make_regression(n_samples=200, n_features=10, n_informative=3, noise=10, random_state=0)
X = StandardScaler().fit_transform(X)

lasso = Lasso(alpha=1.0).fit(X, y)
print(np.round(lasso.coef_, 1))
print("features kept:", int((lasso.coef_ != 0).sum()), "of", X.shape[1])
```

```output
[39.  -0.   8.6  0.   0.  -0.  37.9 -0.  -0.  -0. ]
features kept: 3 of 10
```

Only 3 of the 10 features were truly useful, and Lasso set the weights of the useless ones to exactly zero. **Scale your features before Ridge or Lasso**, because the penalty treats all weights alike and unscaled columns would be punished unfairly.

## How to fight overfitting: a toolbox

| Remedy | Idea |
| --- | --- |
| **more data** | the surest cure, when you can get it |
| **simpler model** | fewer features, shallower trees, lower polynomial degree |
| **regularisation** | Ridge, Lasso, tree depth limits, `min_samples_leaf` |
| **early stopping** | stop training when validation error starts to rise |
| **ensembles** | averaging many models reduces variance (random forests) |
| **dropout** (neural networks) | randomly switch off units during training (the deep learning course) |
| **cross-validation** | honest measurement so you notice overfitting |

## Learning curves: more data or a better model?

Plot the score against the amount of training data:

| What you see | Meaning | What to try |
| --- | --- | --- |
| both curves low and close together | high bias | a more flexible model, better features |
| training high, validation much lower, gap not closing | high variance | more data, regularisation, a simpler model |
| curves converging high | good fit | you are done, or look for gains elsewhere |

`sklearn.model_selection.learning_curve` computes these for you.

:::interview
**Interviewers often ask:** "Explain the bias-variance trade-off." Bias is error from a model that is too simple to capture the pattern; variance is error from a model so flexible it fits noise and changes a lot with the training sample. Increasing complexity lowers bias and raises variance, so we search for the balance with validation. "L1 versus L2?" L2 (Ridge) shrinks weights smoothly; L1 (Lasso) can make weights exactly zero, giving sparse models.
:::
