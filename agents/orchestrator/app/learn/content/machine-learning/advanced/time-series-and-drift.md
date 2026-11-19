---
title: Time series, honest validation and drift
summary: Forecast with lag features, validate by time instead of at random, beat a naive baseline, and notice when real-world data drifts away from your training data.
takeaways:
- Never shuffle time data: always train on the past and test on the future
- Lag and rolling features turn a series into an ordinary table, and a naive baseline gives something to beat
- Models decay as the world changes; monitor for data drift and retrain
---
## What makes time data special

Order matters. Today depends on yesterday, and random splitting lets the model **peek at the future**, a form of leakage that makes the score look far too good.

| Ordinary data | Time-series data |
| --- | --- |
| rows are independent | each row depends on earlier ones |
| shuffle and split at random | split **by time**: train on the past, test on the future |
| any row can be in test | the test set is always the **latest** period |

## A simple series

Daily sales with a trend and a weekly pattern:

```python
import numpy as np
import pandas as pd

rng = np.random.default_rng(0)
days = pd.date_range("2025-01-01", periods=300, freq="D")
trend = np.linspace(100, 160, 300)
weekly = 15 * np.sin(2 * np.pi * np.arange(300) / 7)
sales = pd.Series(trend + weekly + rng.normal(0, 4, 300), index=days)

print(sales.head(3).round(1).to_string())
print("rows:", len(sales))
```

```output
2025-01-01    100.5
2025-01-02    111.4
2025-01-03    117.6
Freq: D
rows: 300
```

## Features from the past

A model needs a table. Create columns from earlier values (**lags**), recent averages (**rolling windows**) and the calendar:

```python
df = pd.DataFrame({"sales": sales})
df["lag_1"] = df["sales"].shift(1)                  # yesterday
df["lag_7"] = df["sales"].shift(7)                  # the same weekday last week
df["rolling_mean_7"] = df["sales"].shift(1).rolling(7).mean()      # average of the last 7 days (not including today)
df["day_of_week"] = df.index.dayofweek
df = df.dropna()

print(df.head(3).round(1).to_string())
```

```output
            sales  lag_1  lag_7  rolling_mean_7  day_of_week
2025-01-08  105.2   94.7  100.5           101.7            2
2025-01-09  110.5  105.2  111.4           102.3            3
2025-01-10  111.4  110.5  117.6           102.2            4
```

Notice `shift(1)` before `rolling`: the average must use only days **before** the one we predict. Including today's value would leak the answer.

## Split by time

```python
split = int(len(df) * 0.8)
train, test = df.iloc[:split], df.iloc[split:]
features = ["lag_1", "lag_7", "rolling_mean_7", "day_of_week"]

print("train:", train.index.min().date(), "to", train.index.max().date())
print("test :", test.index.min().date(), "to", test.index.max().date())
```

```output
train: 2025-01-08 to 2025-08-29
test : 2025-08-30 to 2025-10-27
```

The test period starts **after** the training period ends. That is how the model will be used.

## Beat the baseline first

A **naive forecast** says "tomorrow equals today" (or "the same day last week"). Any model must beat it to be worth using:

```python
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error

naive_yesterday = mean_absolute_error(test["sales"], test["lag_1"])
naive_last_week = mean_absolute_error(test["sales"], test["lag_7"])

linear = LinearRegression().fit(train[features], train["sales"])
forest = RandomForestRegressor(n_estimators=200, random_state=0).fit(train[features], train["sales"])

print("MAE, same as yesterday :", round(naive_yesterday, 1))
print("MAE, same as last week :", round(naive_last_week, 1))
print("MAE, linear regression :", round(mean_absolute_error(test["sales"], linear.predict(test[features])), 1))
print("MAE, random forest     :", round(mean_absolute_error(test["sales"], forest.predict(test[features])), 1))
```

```output
MAE, same as yesterday : 9.2
MAE, same as last week : 5.2
MAE, linear regression : 4.6
MAE, random forest     : 6.0
```

Because sales have a weekly pattern, "same as yesterday" is poor, and "same as last week" is much better. The linear model using lags and the weekday does better still. The forest cannot extrapolate beyond the range of values it saw in training (trees predict averages of training values), so when the series trends upward, tree models can lag behind.

## Why random splits mislead

```python
from sklearn.model_selection import KFold, TimeSeriesSplit, cross_val_score

X, y = df[features], df["sales"]
model = RandomForestRegressor(n_estimators=100, random_state=0)

shuffled = -cross_val_score(model, X, y, cv=KFold(5, shuffle=True, random_state=0), scoring="neg_mean_absolute_error").mean()
forward = -cross_val_score(model, X, y, cv=TimeSeriesSplit(5), scoring="neg_mean_absolute_error").mean()

print("MAE with shuffled folds   :", round(shuffled, 1))
print("MAE with time-ordered folds:", round(forward, 1))
```

```output
MAE with shuffled folds   : 5.1
MAE with time-ordered folds: 6.1
```

Shuffled folds look better, because each test row has neighbours from the future in the training set. `TimeSeriesSplit` always trains on earlier data and tests on later data, giving the honest, larger error you would actually experience.

## Specialised tools

| Tool | Use |
| --- | --- |
| **statsmodels** (ARIMA, SARIMAX, ETS) | classical forecasting with trend and seasonality |
| **Prophet** | quick forecasts with holidays and several seasonalities |
| **sktime**, **darts** | many models behind one interface |
| **LightGBM with lag features** | strong on many series at once |
| **LSTM and Transformers** | deep learning for long, complex series (the deep learning course) |

## Drift: when the world changes

A model is trained on past data and used on future data. If the future stops looking like the past, accuracy decays quietly. This is **drift**.

| Type | Meaning | Example |
| --- | --- | --- |
| **data (covariate) drift** | the inputs change | customers become younger after a campaign |
| **concept drift** | the relationship between inputs and the answer changes | a new law changes what predicts fraud |
| **label drift** | the share of each class changes | more fraud than before |

Check for data drift by comparing a feature's training distribution with recent data, for example with a statistical test:

```python
from scipy.stats import ks_2samp

rng = np.random.default_rng(1)
training_ages = rng.normal(35, 8, 2000)
recent_same = rng.normal(35, 8, 500)
recent_shifted = rng.normal(42, 8, 500)           # the customer base has aged

for name, recent in (("stable week", recent_same), ("drifted week", recent_shifted)):
    result = ks_2samp(training_ages, recent)
    print(f"{name:<13} KS statistic {result.statistic:.3f}  p-value {result.pvalue:.4f}  drift suspected: {result.pvalue < 0.01}")
```

```output
stable week   KS statistic 0.032  p-value 0.8152  drift suspected: False
drifted week  KS statistic 0.383  p-value 0.0000  drift suspected: True
```

The Kolmogorov-Smirnov test asks whether two samples plausibly come from the same distribution. A tiny p-value for the shifted week signals drift. The **Population Stability Index (PSI)** is another popular measure in banks.

## Monitoring checklist

| Monitor | How |
| --- | --- |
| input features | compare recent distributions with training (KS, PSI) |
| predictions | has the share of each predicted class moved? |
| performance | once real outcomes arrive, track accuracy, precision, recall over time |
| data quality | missing values, new categories, out-of-range values |
| business metric | is the model still saving money or catching fraud? |
| a retraining plan | schedule it, or trigger it by an alert; keep the old model to roll back to |

:::interview
**Interviewers often ask:** "How do you validate a time-series model?" Never shuffle: train on earlier data and test on later data, using a forward split or `TimeSeriesSplit`, and compare against a naive baseline. Build features only from information available at prediction time (lags and rolling statistics shifted by one). "What is data drift?" When the distribution of inputs in production changes from the training data, degrading accuracy; detect it with statistical tests and monitoring, and retrain when needed.
:::
