---
title: Feature engineering and data leakage
summary: Turn raw columns into features a model can learn from, build them safely inside a pipeline, and avoid the leakage that makes results look better than they are.
takeaways:
- Good features often matter more than a fancier model
- Fit every transformation on training data only, which a Pipeline does for you
- Data leakage gives beautiful scores that collapse in the real world
---
## Why features matter

A model can only learn from the numbers you give it. A column of raw dates, a city name, or a price that spans six orders of magnitude is hard to learn from. **Feature engineering** turns raw data into inputs that make the pattern easier to see. In many real projects, a few well-made features beat switching to a more complex algorithm.

| Raw data | Better features |
| --- | --- |
| a date such as `2026-03-14` | month, day of week, is it a weekend, days since signup |
| a city name | one-hot columns, or the city's average income |
| a price from 100 to 10,000,000 | the **logarithm** of the price |
| height and weight | **BMI** = weight / height² (a combination) |
| a free-text address | the pin code, the state |
| a user's list of purchases | count, total, average, days since the last one |

## Encoding categories and scaling numbers

Models need numbers. Categories become **one-hot** columns, numbers are **scaled**, and a `ColumnTransformer` applies the right treatment to each column in one step:

```python
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

df = pd.DataFrame({
    "city": ["Chennai", "Madurai", "Chennai", "Salem", "Madurai", "Chennai"],
    "age": [22, 35, 41, 29, 52, 31],
    "income": [25000, 48000, 120000, 38000, 900000, 61000],
})

df["log_income"] = np.log10(df["income"])                  # tame the huge range
df["income_per_year_of_age"] = df["income"] / df["age"]    # a combined feature

prep = ColumnTransformer([
    ("cat", OneHotEncoder(handle_unknown="ignore"), ["city"]),
    ("num", StandardScaler(), ["age", "log_income", "income_per_year_of_age"]),
])
X = prep.fit_transform(df)

print(X.shape)
print(list(prep.get_feature_names_out()))
print(np.round(X[:2], 2))
```

```output
(6, 6)
['cat__city_Chennai', 'cat__city_Madurai', 'cat__city_Salem', 'num__age', 'num__log_income', 'num__income_per_year_of_age']
[[ 1.    0.    0.   -1.36 -1.01 -0.55]
 [ 0.    1.    0.    0.   -0.45 -0.51]]
```

The 6 rows now have 3 city columns plus 3 scaled numeric columns, 6 features in all. Notice `handle_unknown="ignore"`: if a new city appears when the model is used later, it gets all zeros instead of crashing.

## The log transform in action

```python
income = df["income"]
print("raw     :", int(income.min()), "to", int(income.max()))
print("log10   :", round(float(np.log10(income.min())), 2), "to", round(float(np.log10(income.max())), 2))
```

```output
raw     : 25000 to 900000
log10   : 4.4 to 5.95
```

A value of 900,000 is 36 times the smallest, but on the log scale it is only about 1.35 times larger, so a few giant values no longer dominate the model.

## Dates

```python
dates = pd.to_datetime(pd.Series(["2026-03-14", "2026-03-15", "2026-12-25"]))
parts = pd.DataFrame({
    "month": dates.dt.month,
    "day_of_week": dates.dt.dayofweek,        # Monday = 0
    "is_weekend": (dates.dt.dayofweek >= 5).astype(int),
})
print(parts)
```

```output
   month  day_of_week  is_weekend
0      3            5           1
1      3            6           1
2     12            4           0
```

Seasonal patterns (sales in December, traffic on weekends) are invisible in a raw date but obvious in these columns.

## The golden rule: fit on training data only

Scalers and encoders **learn** something (the mean, the categories). If they learn it from the **whole** dataset, information from the test rows leaks into training. Put them in a `Pipeline` and let cross-validation refit them inside each fold:

```python
from sklearn.datasets import load_breast_cancer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import make_pipeline

data = load_breast_cancer()
pipe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
scores = cross_val_score(pipe, data.data, data.target, cv=5)
print(np.round(scores, 3))
print("mean accuracy:", round(float(scores.mean()), 3))
```

```output
[0.982 0.982 0.974 0.974 0.991]
mean accuracy: 0.981
```

Each fold fits the scaler on its own training part, then applies it to its own validation part, which is exactly how the model will be used on new data.

## Data leakage: the silent score inflator

**Leakage** means the model sees information during training that it will **not have** when making real predictions. The score looks wonderful and the model fails in production. Common forms:

| Leak | Example |
| --- | --- |
| **target leakage** | predicting whether a loan defaults using a column "number of collection calls made" (calls happen **after** a default) |
| **train-test contamination** | scaling or choosing features using the whole dataset before splitting |
| **duplicates across the split** | the same customer in both train and test |
| **time leakage** | using the future to predict the past (the time-series lesson) |

See the effect of one leaky column:

```python
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier

X, y = make_classification(n_samples=600, n_features=8, n_informative=3, flip_y=0.15, random_state=0)
model = RandomForestClassifier(n_estimators=100, random_state=0)

honest = cross_val_score(model, X, y, cv=5).mean()

rng = np.random.default_rng(0)
leak = (y + rng.normal(0, 0.1, size=len(y))).reshape(-1, 1)        # a column that secretly encodes the answer
leaky = cross_val_score(model, np.hstack([X, leak]), y, cv=5).mean()

print("honest accuracy:", round(float(honest), 3))
print("leaky accuracy :", round(float(leaky), 3))
```

```output
honest accuracy: 0.83
leaky accuracy : 1.0
```

The leaky version looks perfect, but it is cheating: in real life that column would not exist at prediction time. **If a score looks too good to be true, suspect leakage first.**

## A checklist

| Question | Why |
| --- | --- |
| Would I have this value **at the moment of prediction**? | catches target and time leakage |
| Are all transformations inside the Pipeline? | catches contamination |
| Could the same person or item appear in train and test? | split by group instead (`GroupKFold`) |
| Does one feature dominate suspiciously? | a near-perfect single feature is a warning |
| Is my validation like the real future? | for time data, split by time |

:::tip
Start simple: clean the data, encode, scale, and get a baseline score. Then add **one feature idea at a time** and keep it only if cross-validated performance improves. Ideas come from understanding the problem, so talk to the people who know the domain.
:::
