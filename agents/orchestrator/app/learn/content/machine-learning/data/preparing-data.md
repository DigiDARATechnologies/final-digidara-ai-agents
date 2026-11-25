---
title: Preparing data
summary: Turn raw data into something a model can use: fill gaps, encode categories, scale numbers and split properly.
takeaways:
- Models need numbers, with no missing values
- Encode categories with one-hot columns
- Scale features, but learn the scale from the training data only
---
## Models only understand numbers

Real data has gaps, words and wildly different scales. Before training you fix three things.

## 1. Missing values

```python
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer

df = pd.DataFrame({
    "age": [25, 32, np.nan, 41, 29],
    "salary": [30000, 52000, 41000, np.nan, 38000],
    "city": ["Chennai", "Madurai", "Chennai", "Salem", "Madurai"],
    "bought": [0, 1, 0, 1, 1],
})

imputer = SimpleImputer(strategy="median")
df[["age", "salary"]] = imputer.fit_transform(df[["age", "salary"]])
print(df[["age", "salary"]])
```

```output
    age   salary
0  25.0  30000.0
1  32.0  52000.0
2  30.5  41000.0
3  41.0  39500.0
4  29.0  38000.0
```

The gaps are filled with the **median** of each column.

## 2. Text categories: one-hot encoding

A model cannot use "Chennai". Turn each category into its own 0/1 column:

```python
encoded = pd.get_dummies(df, columns=["city"], dtype=int)
print(encoded)
```

```output
    age   salary  bought  city_Chennai  city_Madurai  city_Salem
0  25.0  30000.0       0             1             0           0
1  32.0  52000.0       1             0             1           0
2  30.5  41000.0       0             1             0           0
3  41.0  39500.0       1             0             0           1
4  29.0  38000.0       1             0             1           0
```

:::warning
Do **not** turn cities into 0, 1, 2, 3 and feed those in. The model would think Salem (3) is "more" than Chennai (0). One-hot columns avoid that false order.
:::

## 3. Scaling

`salary` is in the tens of thousands while `age` is under 100. Many models (like KNN) are thrown off by large numbers. **Standardising** gives each column an average of 0 and a spread of 1:

```python
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
scaled = scaler.fit_transform(df[["age", "salary"]])
print(scaled.round(2))
print(scaled.mean(axis=0).round(2), scaled.std(axis=0).round(2))
```

```output
[[-1.23 -1.43]
 [ 0.09  1.69]
 [-0.19  0.13]
 [ 1.8  -0.08]
 [-0.47 -0.3 ]]
[-0.  0.] [1. 1.]
```

## The rule that prevents cheating

Split **first**. Then learn the scaling (and the fill values) from the **training** data only, and apply the same numbers to the test data:

```python
from sklearn.model_selection import train_test_split

X = df[["age", "salary"]]
y = df["bought"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.4, random_state=1)

scaler = StandardScaler().fit(X_train)        # learn from training only
X_train_s = scaler.transform(X_train)
X_test_s = scaler.transform(X_test)           # reuse the same numbers
print(X_train_s.shape, X_test_s.shape)
```

```output
(3, 2) (2, 2)
```

If you scaled **before** splitting, information about the test rows would leak into training, and your score would look better than it really is. This is called **data leakage**. The Pipelines lesson shows how to avoid it automatically.

## Checklist

| Problem | Fix |
| --- | --- |
| Missing values | `SimpleImputer` (mean, median, most_frequent) |
| Text categories | `pd.get_dummies` or `OneHotEncoder` |
| Very different scales | `StandardScaler` or `MinMaxScaler` |
| Which rows to test on | `train_test_split`, before fitting anything |

:::interview
**Interviewers often ask:** "What is data leakage?" When information from outside the training data (for example the test set) is used to build the model, so the evaluation is too optimistic. Fit scalers and imputers on the training data only.
:::
