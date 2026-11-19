---
title: Frame the question and load the data
summary: Start a data analysis project the professional way: write the business questions first, then load the data and inspect it before touching it.
takeaways:
- Start with the questions the business wants answered, not with the data
- Always inspect the data first: size, types, missing values, ranges
- Keep the raw file untouched and do your work on copies
---
## The scenario

A small retail company with shops in four Tamil Nadu cities sold electronics, clothing, groceries and books during 2025. The owner says:

> "I have a spreadsheet of last year's orders. I do not know where we make money or where to focus next year. Can you tell me?"

That is a typical request: vague, and exactly the kind of work a junior data analyst does. This project takes you through the whole job: **frame, load, clean, analyse, visualise, recommend, present.**

## Step 1: turn the request into questions

A good analyst first converts "tell me about our sales" into **specific, answerable questions**:

| Question | What it will tell the owner |
| --- | --- |
| 1. How much did we sell each month? Is there a trend or a season? | when to stock up and when to run offers |
| 2. Which cities bring the most revenue? | where to focus |
| 3. Which product categories sell best? | what to stock |
| 4. What is the average order value? | how big a typical sale is |
| 5. Do discounts help, i.e. do discounted orders bring in more? | whether offers are worth it |

Writing the questions first stops you from drowning in charts that nobody asked for.

## Step 2: create the practice data

In a real job you would receive a file such as `sales_raw.csv`. So that this project is repeatable on any computer, we generate a realistic **practice dataset** with some typical problems deliberately included (missing cities, duplicates, inconsistent spelling, a few impossible values). We save it as a CSV, just as you would receive it.

```python
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
n = 600

cities = rng.choice(["Chennai", "Madurai", "Salem", "Coimbatore"], size=n, p=[0.40, 0.20, 0.15, 0.25])
categories = rng.choice(["Electronics", "Clothing", "Groceries", "Books"], size=n, p=[0.20, 0.30, 0.35, 0.15])
base_price = {"Electronics": 9000, "Clothing": 1200, "Groceries": 350, "Books": 450}
price = np.array([base_price[c] for c in categories]) * rng.uniform(0.7, 1.3, size=n)
quantity = rng.integers(1, 6, size=n)
discount = rng.choice([0, 5, 10, 20], size=n, p=[0.5, 0.2, 0.2, 0.1])
order_date = pd.to_datetime("2025-01-01") + pd.to_timedelta(rng.integers(0, 365, size=n), unit="D")

sales = pd.DataFrame({
    "order_id": [f"ORD{1000 + i}" for i in range(n)],
    "order_date": order_date.strftime("%Y-%m-%d"),
    "city": cities,
    "category": categories,
    "quantity": quantity,
    "unit_price": price.round(2),
    "discount_pct": discount,
})

# --- real-world mess: this is what raw files look like ---
sales.loc[rng.choice(n, 8, replace=False), "city"] = None                       # missing cities
messy = rng.choice(n, 12, replace=False)
sales.loc[messy[:6], "city"] = sales.loc[messy[:6], "city"].astype(str).str.lower() + " "      # "chennai " (lower case, trailing space)
sales.loc[rng.choice(n, 3, replace=False), "quantity"] = -1                      # impossible quantity
sales = pd.concat([sales, sales.sample(5, random_state=1)], ignore_index=True)   # 5 duplicated rows

sales.to_csv("sales_raw.csv", index=False)
print("saved sales_raw.csv with", len(sales), "rows")
```

```output
saved sales_raw.csv with 605 rows
```

## Step 3: load and inspect

Never start analysing before you have **looked** at the data.

```python
df = pd.read_csv("sales_raw.csv")

print(df.shape)
print()
print(df.head())
```

```output
(605, 7)

  order_id  order_date        city   category  quantity  unit_price  discount_pct
0  ORD1000  2025-11-07  Coimbatore   Clothing         3     1247.82            10
1  ORD1001  2025-09-09     Madurai  Groceries         4      360.69             0
2  ORD1002  2025-09-03  Coimbatore      Books         1      538.71            10
3  ORD1003  2025-07-14       Salem  Groceries         4      394.21            20
4  ORD1004  2025-01-10     Chennai      Books         5      322.18             5
```

```python
print(df.dtypes)
print()
print(df.isna().sum())
```

```output
order_id         object
order_date       object
city             object
category         object
quantity          int64
unit_price      float64
discount_pct      int64
dtype: object

order_id        0
order_date      0
city            8
category        0
quantity        0
unit_price      0
discount_pct    0
dtype: int64
```

The checks above tell you:

- **Shape:** how many rows and columns (605 rows here: 600 orders plus 5 duplicates).
- **Types:** `order_date` is stored as text (`object`), not as a real date, which we must fix.
- **Missing values:** the `city` column has gaps.

## Step 4: look at the numbers and categories

```python
print(df[["quantity", "unit_price", "discount_pct"]].describe().round(1))
print()
print(df["city"].value_counts(dropna=False))
print()
print(df["category"].value_counts())
```

```output
       quantity  unit_price  discount_pct
count     605.0       605.0         605.0
mean        2.9      2429.2           5.0
std         1.4      3487.4           6.3
min        -1.0       245.2           0.0
25%         2.0       375.0           0.0
50%         3.0       867.8           5.0
75%         4.0      1450.8          10.0
max         5.0     11668.0          20.0

city
Chennai        235
Coimbatore     151
Madurai        120
Salem           85
NaN              8
chennai          3
madurai          1
coimbatore       1
salem            1
Name: count, dtype: int64

category
Groceries      198
Clothing       179
Electronics    126
Books          102
Name: count, dtype: int64
```

Reading it like an analyst:

| Observation | Meaning |
| --- | --- |
| `quantity` has a minimum of **-1** | impossible: a data-entry error or a return recorded badly |
| `city` shows `chennai ` (lower case with a space) as a separate group from `Chennai` | inconsistent spelling that would split one city into two |
| `city` has missing values | we must decide what to do with those rows |
| prices range widely (electronics cost more than books) | expected, but check for extreme values later |

## Step 5: protect the original

```py
sales_raw.csv   ->  never edit this file
sales_clean.csv ->  the cleaned copy we will create next
```

The raw file is your **evidence**. If someone asks "why is this number different from my spreadsheet?", you can go back to the original. Do all cleaning in code, so that every change is **recorded and repeatable**, never by hand-editing cells.

## What you have so far

| Done | Next |
| --- | --- |
| questions written | clean the data |
| data loaded and inspected | analyse |
| problems listed | visualise and recommend |

:::tip
Keep a short **analysis log** (a text file or notebook markdown cells) of every decision: "Removed 5 duplicate rows. Set 3 impossible quantities aside." In an interview or review, this log is proof that you work carefully.
:::
