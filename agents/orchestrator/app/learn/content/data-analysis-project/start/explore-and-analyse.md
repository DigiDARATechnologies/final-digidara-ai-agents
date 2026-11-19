---
title: Explore and analyse
summary: Answer each business question with groupby, pivot tables and simple statistics, in clear steps with the numbers checked.
takeaways:
- Turn each question into a groupby: group, calculate, sort
- Always check that parts add up to the whole
- Use percentages and averages as well as totals so that the numbers can be compared
---
## Load the clean data

```python
import pandas as pd

df = pd.read_csv("sales_clean.csv", parse_dates=["order_date"])
print(df.shape)
print("total revenue:", round(df["revenue"].sum(), 2))
print("orders:", df["order_id"].nunique())
print("average order value:", round(df["revenue"].mean(), 2))
```

```output
(597, 10)
total revenue: 3965460.2
orders: 597
average order value: 6642.31
```

These are the **headline numbers**: put them at the top of any report so the reader has the scale.

## Question 1: sales by month

```python
monthly = df.groupby("month")["revenue"].agg(revenue="sum", orders="count").round(0)
monthly["avg_order"] = (monthly["revenue"] / monthly["orders"]).round(0)
print(monthly.to_string())

best = monthly["revenue"].idxmax()
worst = monthly["revenue"].idxmin()
print()
print("best month :", best, f"({monthly.loc[best, 'revenue']:,.0f})")
print("worst month:", worst, f"({monthly.loc[worst, 'revenue']:,.0f})")
```

```output
          revenue  orders  avg_order
month
2025-01  247205.0      44     5618.0
2025-02  349234.0      53     6589.0
2025-03  507006.0      58     8741.0
2025-04  345623.0      48     7200.0
2025-05  194182.0      43     4516.0
2025-06   80026.0      44     1819.0
2025-07  393327.0      67     5871.0
2025-08  312651.0      50     6253.0
2025-09  432134.0      51     8473.0
2025-10  345554.0      48     7199.0
2025-11  242800.0      45     5396.0
2025-12  515719.0      46    11211.0

best month : 2025-12 (515,719)
worst month: 2025-06 (80,026)
```

A table of the twelve months shows the pattern of the year. This data was generated randomly, so any "season" we see is partly luck. With real data, first check **how many orders** each month has before reading too much into the ups and downs.

## Question 2: which cities bring the most revenue?

```python
by_city = df.groupby("city")["revenue"].agg(revenue="sum", orders="count")
by_city["avg_order"] = (by_city["revenue"] / by_city["orders"]).round(0)
by_city["share_pct"] = (100 * by_city["revenue"] / by_city["revenue"].sum()).round(1)
by_city = by_city.sort_values("revenue", ascending=False)
print(by_city.round(0).to_string())
print()
print("shares add up to:", round(by_city["share_pct"].sum(), 1), "%")
```

```output
              revenue  orders  avg_order  share_pct
city
Chennai     1587397.0     234     6784.0       40.0
Coimbatore  1031308.0     149     6922.0       26.0
Madurai      730349.0     120     6086.0       18.0
Salem        562158.0      86     6537.0       14.0
Unknown       54248.0       8     6781.0        1.0

shares add up to: 100.0 %
```

Do not look only at totals. A city with more orders is not necessarily a city with **bigger** orders, so we also calculated the **average order** and the **share** of total revenue. The check at the end (the shares add up to 100%) catches mistakes in the calculation.

## Question 3: which categories sell best?

```python
by_category = df.groupby("category").agg(
    revenue=("revenue", "sum"),
    orders=("order_id", "count"),
    units=("quantity", "sum"),
)
by_category["share_pct"] = (100 * by_category["revenue"] / by_category["revenue"].sum()).round(1)
by_category["revenue_per_order"] = (by_category["revenue"] / by_category["orders"]).round(0)
print(by_category.sort_values("revenue", ascending=False).round(0).to_string())
```

```output
               revenue  orders  units  share_pct  revenue_per_order
category
Electronics  3023371.0     123    356       76.0            24580.0
Clothing      624699.0     178    546       16.0             3510.0
Groceries     184859.0     194    560        5.0              953.0
Books         132531.0     102    302        3.0             1299.0
```

This table shows the important contrast: a category can sell the most **units or orders** and still bring in much less **money** than an expensive category. That is exactly the kind of insight a shop owner needs.

## City and category together: a pivot table

```python
pivot = df.pivot_table(index="city", columns="category", values="revenue", aggfunc="sum", fill_value=0).round(0)
pivot["Total"] = pivot.sum(axis=1)
print((pivot / 1000).round(0).astype(int).to_string())
print("\n(in thousands of rupees)")
```

```output
category    Books  Clothing  Electronics  Groceries  Total
city
Chennai        54       217         1247         68   1587
Coimbatore     28       169          781         52   1031
Madurai        30       146          519         36    730
Salem          17        87          431         27    562
Unknown         3         5           45          1     54

(in thousands of rupees)
```

A pivot table is the same as an Excel pivot: cities down the side, categories across the top, revenue in the middle. It lets you see **where each product sells**.

## Question 5: do discounts help?

Compare orders with and without a discount:

```python
df["discounted"] = df["discount_pct"] > 0
summary = df.groupby("discounted").agg(
    orders=("order_id", "count"),
    avg_quantity=("quantity", "mean"),
    avg_revenue=("revenue", "mean"),
)
print(summary.round(2).to_string())

by_level = df.groupby("discount_pct").agg(orders=("order_id", "count"), avg_quantity=("quantity", "mean"), avg_revenue=("revenue", "mean"))
print()
print(by_level.round(2).to_string())
```

```output
            orders  avg_quantity  avg_revenue
discounted
False          292          2.88      6894.01
True           305          3.03      6401.34

              orders  avg_quantity  avg_revenue
discount_pct
0                292          2.88      6894.01
5                123          2.98      5204.30
10               125          3.10      7428.92
20                57          2.98      6730.99
```

If discounts really helped, discounted orders would show larger **quantities** (people buy more because it is cheaper). Compare the average quantity in each row. Remember the lesson from statistics: **correlation is not causation**. In real life, you would need an experiment (an A/B test) to prove that a discount **caused** a change.

## Weekday pattern

```python
order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
weekday = df.groupby("weekday")["revenue"].agg(["count", "sum"]).reindex(order)
weekday["share_pct"] = (100 * weekday["sum"] / weekday["sum"].sum()).round(1)
print(weekday.round(0).to_string())
```

```output
           count       sum  share_pct
weekday
Monday        91  689794.0       17.0
Tuesday       81  389569.0       10.0
Wednesday     84  480601.0       12.0
Thursday      77  587066.0       15.0
Friday        76  500897.0       13.0
Saturday      97  756241.0       19.0
Sunday        91  561291.0       14.0
```

Use `reindex` with a list to get the days in calendar order instead of alphabetical.

## Good analysis habits

| Habit | Why |
| --- | --- |
| **check that totals match** (shares add up to 100%, city totals equal the grand total) | catches mistakes early |
| **use averages and percentages alongside totals** | allows fair comparison |
| **look at counts** before trusting an average | an average of 3 orders means little |
| **name your measures** (revenue, average order value) and define them once | consistent numbers |
| **save intermediate tables** when needed | easy to rerun and to explain |
| **write down surprises** | they are the insights |

:::interview
**Interviewers often ask:** "How would you find out which product category is most profitable?" Revenue is not profit. You would need the cost of each product, then compute `profit = revenue minus cost`, group by category, and compare profit **margin** as well as total profit. Mentioning this difference shows business thinking.
:::
