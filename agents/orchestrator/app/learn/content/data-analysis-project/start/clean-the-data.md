---
title: Clean the data
summary: Fix the problems found in the inspection: duplicates, inconsistent text, missing values, impossible numbers and wrong types, and keep a record of each decision.
takeaways:
- Cleaning is usually the biggest part of an analysis; do it carefully and record every step
- Decide what to do with each problem (fix, fill, remove or flag), and explain why
- Compare counts before and after so you know exactly what changed
---
## The cleaning plan

From the inspection we have five problems. For each, decide the treatment:

| Problem | Treatment | Reason |
| --- | --- | --- |
| duplicate rows | remove | the same order counted twice would inflate revenue |
| text with different case and spaces (`chennai `) | standardise | one city must be one group |
| missing city | label as "Unknown" | the order is real revenue; dropping it would understate sales |
| impossible quantity (-1) | remove those rows | we cannot know the true quantity, and only 3 rows are affected |
| `order_date` stored as text | convert to a real date | needed for monthly analysis |

Keep a running record of how many rows we have:

```python
import pandas as pd

df = pd.read_csv("sales_raw.csv")
log = [("raw data", len(df))]

# 1. remove exact duplicate rows
df = df.drop_duplicates()
log.append(("after removing duplicates", len(df)))

# 2. standardise the city text: strip spaces and use a consistent capitalisation
df["city"] = df["city"].str.strip().str.title()
print(sorted(df["city"].dropna().unique()))

# 3. fill missing cities with a clear label
missing_cities = int(df["city"].isna().sum())
df["city"] = df["city"].fillna("Unknown")
print("missing cities labelled 'Unknown':", missing_cities)

# 4. remove impossible quantities
bad_quantity = int((df["quantity"] <= 0).sum())
df = df[df["quantity"] > 0]
log.append(("after removing impossible quantities", len(df)))
print("rows removed for impossible quantity:", bad_quantity)

# 5. convert the date column to real dates
df["order_date"] = pd.to_datetime(df["order_date"])

for step, rows in log:
    print(f"{step:<40} {rows:>5} rows")
```

```output
['Chennai', 'Coimbatore', 'Madurai', 'Salem']
missing cities labelled 'Unknown': 8
rows removed for impossible quantity: 3
raw data                                   605 rows
after removing duplicates                  600 rows
after removing impossible quantities       597 rows
```

The log shows **exactly** what each step removed: 5 duplicates, then 3 impossible quantities. If anyone doubts the result, they can see the steps.

## Check that the cleaning worked

Never assume. Verify with checks:

```python
print("duplicates left        :", int(df.duplicated().sum()))
print("missing values per column:")
print(df.isna().sum().to_string())
print("smallest quantity       :", int(df["quantity"].min()))
print("cities now              :", sorted(df["city"].unique()))
print("date range              :", df["order_date"].min().date(), "to", df["order_date"].max().date())
print("date column type        :", df["order_date"].dtype)
```

```output
duplicates left        : 0
missing values per column:
order_id        0
order_date      0
city            0
category        0
quantity        0
unit_price      0
discount_pct    0
smallest quantity       : 1
cities now              : ['Chennai', 'Coimbatore', 'Madurai', 'Salem', 'Unknown']
date range              : 2025-01-01 to 2025-12-31
date column type        : datetime64[ns]
```

The city names are consistent, there are no duplicates or missing values, the quantities are all positive, and the dates are real dates covering the year.

## Create the columns we need

Raw columns rarely answer the question directly. Create the **revenue** of each order and the **month**:

```python
df["revenue"] = (df["quantity"] * df["unit_price"] * (1 - df["discount_pct"] / 100)).round(2)
df["month"] = df["order_date"].dt.to_period("M").astype(str)
df["weekday"] = df["order_date"].dt.day_name()

print(df[["order_id", "quantity", "unit_price", "discount_pct", "revenue", "month"]].head(3))
print()
print("total revenue:", round(df["revenue"].sum(), 2))
```

```output
  order_id  quantity  unit_price  discount_pct  revenue    month
0  ORD1000         3     1247.82            10  3369.11  2025-11
1  ORD1001         4      360.69             0  1442.76  2025-09
2  ORD1002         1      538.71            10   484.84  2025-09

total revenue: 3965460.2
```

Revenue is quantity times price, after taking off the discount percentage. We create it **once** here so that every later calculation uses the same definition.

## Look for outliers

An outlier is a value far from the rest. It may be an error, or a real big sale. Check before trusting averages:

```python
q1, q3 = df["revenue"].quantile([0.25, 0.75])
upper_fence = q3 + 1.5 * (q3 - q1)
outliers = df[df["revenue"] > upper_fence]

print("upper fence (Q3 + 1.5 x IQR):", round(upper_fence, 2))
print("orders above the fence:", len(outliers), "of", len(df))
print(outliers["category"].value_counts().to_string())
```

```output
upper fence (Q3 + 1.5 x IQR): 12486.56
orders above the fence: 91 of 597
category
Electronics    91
```

All of the orders above the fence are electronics, which is normal for expensive items bought in quantity: **real sales, not errors**, so we keep them. If we found a 5,000,000 order for a book, that would be a different story. Always ask "is this an error or genuine?" before removing outliers.

## Save the cleaned data

```python
df.to_csv("sales_clean.csv", index=False)
print("saved sales_clean.csv:", df.shape)
```

```output
saved sales_clean.csv: (597, 10)
```

From here on we analyse `sales_clean.csv`. The raw file is untouched.

## The cleaning checklist

| Check | Done |
| --- | --- |
| duplicates removed (and counted) | yes |
| text standardised (spaces, case, spelling) | yes |
| missing values handled and explained | yes |
| impossible values removed or fixed | yes |
| data types corrected (dates, numbers) | yes |
| outliers examined, not blindly removed | yes |
| new columns created with clear definitions | yes |
| before and after counts recorded | yes |

:::warning
Do not silently delete rows because they are inconvenient. Every row you remove changes the answer. State how many you removed and why, and tell the reader if the removed rows could change the conclusion.
:::
