---
title: Exploring data visually (EDA)
summary: Use charts and simple checks to understand a new dataset: missing values, outliers, distributions and relationships, before you build any model.
takeaways:
- Exploratory data analysis (EDA) means looking at the data before modelling it
- Check missing values, spread, outliers, balance of classes and links between columns
- Write down what you find; the notes guide cleaning and modelling
---
## What EDA is

**Exploratory data analysis** is the first conversation with your data. You ask simple questions and answer them with tables and charts:

| Question | Tool |
| --- | --- |
| how big is it, what types? | `df.shape`, `df.info()` |
| is anything missing? | `df.isna().sum()`, a missing-value chart |
| how is each number spread? | histogram, box plot, `describe()` |
| are there outliers? | box plot, the IQR rule |
| how are categories balanced? | `value_counts()`, count plot |
| which columns relate? | scatter plot, correlation heat map |

## A messy dataset to explore

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

rng = np.random.default_rng(3)
n = 300
df = pd.DataFrame({
    "age": rng.integers(18, 60, n).astype(float),
    "monthly_income": rng.normal(42000, 12000, n).round(0),
    "spend": rng.normal(15000, 5000, n).round(0),
    "city": rng.choice(["Chennai", "Madurai", "Salem"], n, p=[0.5, 0.3, 0.2]),
})
df.loc[rng.choice(n, 25, replace=False), "monthly_income"] = np.nan          # missing values
df.loc[rng.choice(n, 4, replace=False), "monthly_income"] = 400000           # suspicious huge incomes

print(df.shape)
print(df.dtypes.to_string())
```

```output
(300, 4)
age               float64
monthly_income    float64
spend             float64
city               object
```

## Step 1: missing values

```python
missing = df.isna().sum()
percent = (100 * missing / len(df)).round(1)
print(pd.DataFrame({"missing": missing, "percent": percent}).to_string())
```

```output
                missing  percent
age                   0      0.0
monthly_income       24      8.0
spend                 0      0.0
city                  0      0.0
```

A bar chart of these percentages (or `sns.heatmap(df.isna())`) shows quickly which columns need attention. What to do depends on how much is missing and why: fill with the median, fill with a label, or drop the rows.

## Step 2: spread and outliers

```python
print(df["monthly_income"].describe().round(0).to_string())

q1, q3 = df["monthly_income"].quantile([0.25, 0.75])
iqr = q3 - q1
upper, lower = q3 + 1.5 * iqr, q1 - 1.5 * iqr
outliers = df[(df["monthly_income"] > upper) | (df["monthly_income"] < lower)]
print(f"\noutlier fences: {lower:,.0f} to {upper:,.0f}")
print("rows outside the fences:", len(outliers))
print("their incomes:", sorted(outliers["monthly_income"].astype(int).tolist())[-5:])
```

```output
count       276.0
mean      48218.0
std       44265.0
min        5299.0
25%       35405.0
50%       43560.0
75%       51309.0
max      400000.0

outlier fences: 11,549 to 75,165
rows outside the fences: 7
their incomes: [76970, 400000, 400000, 400000, 400000]
```

The maximum is far above the 75th percentile, a typical sign of outliers. The IQR rule flags 7 rows: the four large incomes we planted, and three ordinary-looking values that sit just outside the fences (76,970 for example). A rule gives you **candidates**, and you decide which are real problems. A box plot would draw all of them as dots beyond the whiskers.

**Do not delete outliers blindly.** Ask whether each is a typing error (remove or fix it) or a real, rare value (keep it). Here 400,000 for a monthly income in this dataset is probably an error.

## Step 3: distributions

```python
clean = df["monthly_income"].dropna()
clean = clean[clean < upper]
counts, edges = np.histogram(clean, bins=8)
for count, low, high in zip(counts, edges[:-1], edges[1:]):
    print(f"{low:8,.0f} to {high:8,.0f} | {'#' * (count // 3)} {count}")
```

```output
   5,299 to   13,386 |  2
  13,386 to   21,472 | ### 9
  21,472 to   29,559 | ######## 26
  29,559 to   37,646 | ############### 47
  37,646 to   45,733 | ########################## 78
  45,733 to   53,820 | ##################### 64
  53,820 to   61,906 | ########### 34
  61,906 to   69,993 | ### 11
```

After removing the outliers, the income values form a bell shape around 42,000: symmetric, so the mean and median agree.

## Step 4: categories and balance

```python
print(df["city"].value_counts(normalize=True).round(2).to_string())
print()
print(df.groupby("city")["spend"].agg(["count", "mean"]).round(0).to_string())
```

```output
city
Chennai    0.50
Madurai    0.31
Salem      0.19

         count     mean
city
Chennai    151  15243.0
Madurai     92  15886.0
Salem       57  15008.0
```

If one class were tiny (for example 1% fraud), you would need the imbalance tools from the Machine Learning course.

## Step 5: relationships

```python
numeric = df[["age", "monthly_income", "spend"]].copy()
numeric.loc[numeric["monthly_income"] > upper, "monthly_income"] = np.nan
print(numeric.corr().round(2).to_string())
```

```output
                 age  monthly_income  spend
age             1.00            0.07  -0.08
monthly_income  0.07            1.00   0.01
spend          -0.08            0.01   1.00
```

The correlations are all near zero because this data is random. In real data you would look for strong links (a candidate feature for a model) and for features that repeat each other.

## Write down what you found

| Finding | Action |
| --- | --- |
| `monthly_income` has 8% missing | fill with the median |
| 4 incomes above 400,000 look like errors | check the source; remove or correct |
| Chennai has half the customers | keep the balance in mind when comparing cities |
| no strong relationship between columns | do not expect an easy prediction |

This list is the real product of EDA: it tells you how to clean the data and what to expect from a model.

:::tip
Make EDA a habit: shape, types, missing values, summary statistics, a histogram of each important number, a count of each category, and a correlation table. Ten minutes here saves hours of confused modelling.
:::
