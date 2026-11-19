---
title: Interpreting models
summary: Open the black box: feature importance, permutation importance, partial dependence and what each one can and cannot tell you.
takeaways:
- Interpretation builds trust, finds bugs and is often required (finance, health)
- Built-in tree importances can mislead; permutation importance on held-out data is more reliable
- Importance shows what the model uses, not what causes the outcome
---
## Why interpret a model?

| Reason | Example |
| --- | --- |
| **Find bugs and leakage** | the top feature is an ID column or something unavailable at prediction time |
| **Trust** | a doctor will not use a model they cannot question |
| **Regulation and fairness** | lenders must explain decisions; check that a protected attribute is not driving results |
| **Learn about the problem** | which factors actually matter |
| **Debug mistakes** | why was this one customer misclassified? |

Interpretation comes in two scales: **global** (how does the model behave overall?) and **local** (why did it give *this* prediction?).

## Simple models explain themselves

A linear model's coefficients show direction and strength, if the features are scaled:

```python
import numpy as np
from sklearn.datasets import load_breast_cancer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

data = load_breast_cancer()
X_train, X_test, y_train, y_test = train_test_split(data.data, data.target, test_size=0.3, random_state=0, stratify=data.target)

linear = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)).fit(X_train, y_train)
coefs = linear.named_steps["logisticregression"].coef_[0]

order = np.argsort(np.abs(coefs))[::-1][:5]
for i in order:
    print(f"{data.feature_names[i]:<25} {coefs[i]:+.2f}")
```

```output
radius error              -1.08
worst texture             -1.07
mean concave points       -1.01
worst radius              -1.00
worst area                -0.88
```

Features with the largest absolute coefficients matter most. The sign says the direction: here a negative sign pushes toward class 0 (malignant) as the measurement grows. Without scaling, the sizes of the coefficients cannot be compared.

## Tree importances and their trap

Random forests offer `feature_importances_`, but they favour features with many distinct values and are computed on **training** data:

```python
from sklearn.ensemble import RandomForestClassifier

forest = RandomForestClassifier(n_estimators=200, random_state=0).fit(X_train, y_train)
importance = forest.feature_importances_
top = np.argsort(importance)[::-1][:5]
for i in top:
    print(f"{data.feature_names[i]:<25} {importance[i]:.3f}")
print("test accuracy:", round(forest.score(X_test, y_test), 3))
```

```output
worst radius              0.133
worst perimeter           0.132
worst concave points      0.128
worst area                0.108
mean concave points       0.098
test accuracy: 0.953
```

Useful as a first look, but treat it with care, especially when features are correlated (importance gets split between them).

## Permutation importance: a fairer test

Idea: take one column and **shuffle** its values, which destroys its relationship to the answer. If the model's score on **held-out data** drops a lot, the model relied on that feature. If nothing changes, the feature did not matter.

```python
from sklearn.inspection import permutation_importance

result = permutation_importance(forest, X_test, y_test, n_repeats=10, random_state=0)
top = np.argsort(result.importances_mean)[::-1][:5]
for i in top:
    print(f"{data.feature_names[i]:<25} drop in accuracy {result.importances_mean[i]:.3f} (+/- {result.importances_std[i]:.3f})")
```

```output
worst radius              drop in accuracy 0.021 (+/- 0.005)
worst area                drop in accuracy 0.019 (+/- 0.007)
worst texture             drop in accuracy 0.016 (+/- 0.004)
worst perimeter           drop in accuracy 0.012 (+/- 0.007)
worst concave points      drop in accuracy 0.012 (+/- 0.008)
```

It works with **any** model, uses data the model has not seen, and gives a number in the units of your score. Its limitation: with strongly correlated features, shuffling one leaves its twin to cover for it, so both can look unimportant.

## Partial dependence: how does a feature change predictions?

Vary one feature across its range while holding everyone else as they are, and average the model's output:

```python
from sklearn.inspection import partial_dependence

feature = list(data.feature_names).index("worst radius")
pd_result = partial_dependence(forest, X_train, [feature], grid_resolution=5)

for value, average in zip(pd_result["grid_values"][0], pd_result["average"][0]):
    print(f"worst radius {value:>6.1f} -> average predicted probability of 'benign' {average:.2f}")
```

```output
worst radius   10.5 -> average predicted probability of 'benign' 0.67
worst radius   14.2 -> average predicted probability of 'benign' 0.67
worst radius   18.0 -> average predicted probability of 'benign' 0.51
worst radius   21.8 -> average predicted probability of 'benign' 0.50
worst radius   25.5 -> average predicted probability of 'benign' 0.50
```

The prediction moves with the feature: as the radius grows, the model's confidence in "benign" drops. Partial dependence shows the **shape** of the effect (steady, flat, thresholds) that a single importance number hides.

## Local explanations: SHAP

For one prediction, tools such as **SHAP** and **LIME** estimate how much each feature pushed that specific answer up or down:

```py
pip install shap
import shap
explainer = shap.TreeExplainer(model)
shap_values = explainer(X_test)
shap.plots.waterfall(shap_values[0])      # why this one patient got this score
shap.plots.beeswarm(shap_values)          # the global picture
```

SHAP is grounded in game theory and is the most widely used method in industry for tree models.

## A summary of the tools

| Tool | Scale | Works on | Watch out for |
| --- | --- | --- | --- |
| coefficients (scaled) | global | linear models | correlated features share credit |
| `feature_importances_` | global | trees, forests | biased to high-cardinality features; training data |
| permutation importance | global | any model | correlated features |
| partial dependence | global (one feature) | any model | hides interactions, can mislead if features correlate |
| SHAP / LIME | local and global | any model | slower; an explanation of the model, not of reality |

:::warning
Importance tells you what the **model** uses, not what **causes** the outcome. A model may rely on ice-cream sales to predict drownings because both rise in summer. Never read a feature's importance as proof that changing it would change the result.
:::

:::interview
**Interviewers often ask:** "How would you explain a black-box model's prediction?" For global behaviour use permutation importance and partial dependence; for one prediction use SHAP or LIME. Check for leakage when a feature looks too important, and remember that importance reflects the model's use of a feature, not causation.
:::
