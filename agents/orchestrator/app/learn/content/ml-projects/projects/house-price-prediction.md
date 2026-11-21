---
title: Project: House price prediction (regression)
summary: Predict a number from several features: explore, compare linear regression, Ridge and a random forest, and measure the error in rupees.
takeaways:
- Regression predicts a number; judge it with RMSE, MAE and R squared, in the units people understand
- Start with a baseline and a linear model, then compare a flexible model
- Check which features matter, and be careful about what the model has not seen
---
## The problem

A property website wants to estimate a fair price from the size, bedrooms, age, distance from the city centre and the city. The target is a **number** (price), so this is **regression**.

## The data

We create a realistic practice dataset (real projects use a listing dataset such as the Kaggle housing data; the method is the same):

```python
import numpy as np
import pandas as pd

rng = np.random.default_rng(11)
n = 1000
city = rng.choice(["Chennai", "Coimbatore", "Madurai"], n, p=[0.5, 0.3, 0.2])
area = rng.normal(1200, 350, n).clip(400, 3000)
bedrooms = np.clip(np.round(area / 450 + rng.normal(0, 0.6, n)), 1, 5).astype(int)
age = rng.integers(0, 30, n)
distance = rng.uniform(1, 25, n)
premium = pd.Series(city).map({"Chennai": 600000, "Coimbatore": 250000, "Madurai": 0}).to_numpy()

price = 4200 * area + 120000 * bedrooms - 15000 * age - 25000 * distance + premium + rng.normal(0, 250000, n)
houses = pd.DataFrame({"city": city, "area_sqft": area.round(0), "bedrooms": bedrooms, "age_years": age, "distance_km": distance.round(1), "price": price.round(-3)})

print(houses.shape)
print(houses.head(3).to_string())
print()
print(houses["price"].describe().round(0).to_string())
```

```output
(1000, 6)
         city  area_sqft  bedrooms  age_years  distance_km      price
0     Chennai      728.0         2          3         10.4  3879000.0
1     Chennai     1272.0         3         24         18.3  5649000.0
2  Coimbatore     1058.0         3         14         21.3  4098000.0

count        1000.0
mean      5204476.0
std       1585967.0
min        976000.0
25%       4102500.0
50%       5184000.0
75%       6270500.0
max      10076000.0
```

## Explore first

```python
print(houses.drop(columns="city").corr()["price"].drop("price").sort_values(ascending=False).round(2).to_string())
print()
print(houses.groupby("city")["price"].mean().round(0).to_string())
```

```output
area_sqft      0.97
bedrooms       0.74
age_years     -0.02
distance_km   -0.10

city
Chennai       5406854.0
Coimbatore    5071466.0
Madurai       4844038.0
```

Area is by far the strongest driver of price (0.97). Age and distance have weak correlations on their own, but the model will find that they still push the price down once area is taken into account. Chennai is more expensive than Coimbatore, which is more expensive than Madurai.

## Baseline, then models

```python
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

X = houses.drop(columns="price")
y = houses["price"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=0)

prep = ColumnTransformer([
    ("city", OneHotEncoder(), ["city"]),
    ("numbers", StandardScaler(), ["area_sqft", "bedrooms", "age_years", "distance_km"]),
])

models = {
    "baseline (always the average)": DummyRegressor(strategy="mean"),
    "linear regression": make_pipeline(prep, LinearRegression()),
    "ridge regression": make_pipeline(prep, Ridge(alpha=10)),
    "random forest": make_pipeline(prep, RandomForestRegressor(n_estimators=200, random_state=0)),
}

print(f"{'model':<30}{'RMSE':>12}{'MAE':>12}{'R2':>8}")
for name, model in models.items():
    model.fit(X_train, y_train)
    predicted = model.predict(X_test)
    rmse = mean_squared_error(y_test, predicted) ** 0.5
    print(f"{name:<30}{rmse:>12,.0f}{mean_absolute_error(y_test, predicted):>12,.0f}{r2_score(y_test, predicted):>8.2f}")
```

```output
model                                 RMSE         MAE      R2
baseline (always the average)    1,513,891   1,216,977   -0.00
linear regression                  255,080     202,414    0.97
ridge regression                   254,628     200,145    0.97
random forest                      311,040     248,393    0.96
```

How to read it:

| Measure | Meaning |
| --- | --- |
| **MAE** | the average size of the mistake, in rupees |
| **RMSE** | like MAE but punishes big mistakes more |
| **R squared** | the share of the price variation the model explains (1 is perfect, 0 is no better than the average) |

The baseline has an R squared near zero. The linear models are far better, and here they match or beat the random forest, because the data really is a straight-line relationship. **A simple model is often the right one**; the forest cannot do better than the truth it is given and may be slightly noisier.

## What does the model say?

```python
linear = models["linear regression"]
names = list(linear.named_steps["columntransformer"].get_feature_names_out())
coefficients = pd.Series(linear.named_steps["linearregression"].coef_, index=names).sort_values(key=abs, ascending=False)
print(coefficients.round(0).to_string())
```

```output
numbers__area_sqft       1483096.0
city__city_Chennai        310352.0
city__city_Madurai       -262793.0
numbers__distance_km     -171249.0
numbers__age_years       -124941.0
numbers__bedrooms         101416.0
city__city_Coimbatore     -47558.0
```

Because the numbers were scaled, the sizes are comparable. Area has the biggest effect, then the city. Each coefficient is the change in price (rupees) for a 1-standard-deviation move in the feature.

## Predict a new house

```python
new_house = pd.DataFrame([{"city": "Chennai", "area_sqft": 1400, "bedrooms": 3, "age_years": 5, "distance_km": 8}])
estimate = linear.predict(new_house)[0]
low, high = estimate - 1.96 * 250000, estimate + 1.96 * 250000
print(f"estimated price: {estimate:,.0f}")
print(f"a reasonable range: {low:,.0f} to {high:,.0f}")
```

```output
estimated price: 6,576,012
a reasonable range: 6,086,012 to 7,066,012
```

Always show a **range**, not just one number: the model's typical error is about a quarter of a million rupees.

## Check the mistakes

```python
residuals = y_test - linear.predict(X_test)
print("average mistake (should be near 0):", round(float(residuals.mean())))
print("largest overestimate :", round(float(residuals.min())))
print("largest underestimate:", round(float(residuals.max())))
```

```output
average mistake (should be near 0): -5871
largest overestimate : -670813
largest underestimate: 799217
```

If the average mistake were far from zero, the model would be biased. Look also at mistakes by city and by price band: a model that is fine on average can be poor for expensive houses.

## Limits to write in your README

| Limit | Note |
| --- | --- |
| practice data | real prices depend on the exact locality, the road, the builder, the season |
| only 3 cities | do not use it for another city |
| only a few features | add floor, parking, amenities, locality |
| straight-line assumption | try a boosting model on real data |
| prices change | retrain regularly |

:::interview
**Interviewers often ask:** "Which metric would you report for a house-price model?" MAE or RMSE, because they are in rupees and meaningful to users, together with R squared for context, and a comparison with a baseline.
:::
