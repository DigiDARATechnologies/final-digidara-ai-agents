---
title: Insights and recommendations
summary: Move from numbers to advice: find the insights, write them in plain language with evidence, say what you are not sure about, and give recommendations the owner can act on.
takeaways:
- An insight is a finding that changes a decision, not just a number
- Write each insight with evidence, and be honest about limits
- A recommendation names an action, the reason and the expected benefit
---
## Data is not the answer; advice is

The owner does not want tables. They want to know **what to do**. The last mile of any analysis is turning numbers into **insights** and **recommendations**.

| Level | Example |
| --- | --- |
| **Data** | "Chennai revenue was 3,100,000." |
| **Information** | "Chennai accounted for 39% of revenue." |
| **Insight** | "Chennai brings the most revenue, but its average order is lower than Coimbatore's: it wins by volume, not by value." |
| **Recommendation** | "Run a bundle offer in Chennai to lift the average order value." |

## Pull the key numbers together

Compute the facts you will quote in one place, so that every number in the report has a source:

```python
import pandas as pd

df = pd.read_csv("sales_clean.csv", parse_dates=["order_date"])
total = df["revenue"].sum()

city = df.groupby("city")["revenue"].agg(revenue="sum", orders="count")
city["avg_order"] = city["revenue"] / city["orders"]
city["share"] = 100 * city["revenue"] / total

category = df.groupby("category")["revenue"].agg(revenue="sum", orders="count")
category["share"] = 100 * category["revenue"] / total

monthly = df.groupby("month")["revenue"].sum()

facts = {
    "total revenue": f"{total:,.0f}",
    "orders": len(df),
    "average order value": f"{df['revenue'].mean():,.0f}",
    "top city": f"{city['revenue'].idxmax()} ({city['share'].max():.0f}% of revenue)",
    "city with biggest average order": f"{city['avg_order'].idxmax()} ({city['avg_order'].max():,.0f})",
    "top category": f"{category['revenue'].idxmax()} ({category['share'].max():.0f}% of revenue)",
    "category with most orders": f"{category['orders'].idxmax()} ({category['orders'].max()} orders)",
    "best month": f"{monthly.idxmax()} ({monthly.max():,.0f})",
    "weakest month": f"{monthly.idxmin()} ({monthly.min():,.0f})",
}
for name, value in facts.items():
    print(f"{name:<34} {value}")
```

```output
total revenue                      3,965,460
orders                             597
average order value                6,642
top city                           Chennai (40% of revenue)
city with biggest average order    Coimbatore (6,922)
top category                       Electronics (76% of revenue)
category with most orders          Groceries (194 orders)
best month                         2025-12 (515,719)
weakest month                      2025-06 (80,026)
```

Everything in the written summary should come from this list. That way the report cannot contain a number that you cannot trace.

## Check for something surprising

Insights often hide where two measures disagree. Compare each category's share of **orders** with its share of **revenue**:

```python
mix = pd.DataFrame({
    "share_of_orders_%": (100 * category["orders"] / category["orders"].sum()).round(1),
    "share_of_revenue_%": category["share"].round(1),
})
mix["revenue_per_order"] = (category["revenue"] / category["orders"]).round(0)
print(mix.sort_values("share_of_revenue_%", ascending=False).to_string())
```

```output
             share_of_orders_%  share_of_revenue_%  revenue_per_order
category
Electronics               20.6                76.2            24580.0
Clothing                  29.8                15.8             3510.0
Groceries                 32.5                 4.7              953.0
Books                     17.1                 3.3             1299.0
```

Look for the mismatch: a category that has a small share of **orders** but a big share of **revenue** is worth protecting; one with many orders but a small revenue share keeps the shop busy without growing sales. This is the kind of finding that changes a decision.

## How confident are we?

Honest analysts say what they are not sure about. Check how much the result depends on a few big orders:

```python
sorted_orders = df["revenue"].sort_values(ascending=False)
top_5_percent = int(len(df) * 0.05)
share_of_top = 100 * sorted_orders.head(top_5_percent).sum() / total
print(f"the biggest {top_5_percent} orders (5% of all orders) make up {share_of_top:.0f}% of revenue")

electronics_share = 100 * df.loc[df["category"] == "Electronics", "revenue"].sum() / total
print(f"electronics alone is {electronics_share:.0f}% of revenue")
```

```output
the biggest 29 orders (5% of all orders) make up 32% of revenue
electronics alone is 76% of revenue
```

When a small number of large orders drives revenue, **a single lost customer could change the picture**. That is a risk to mention to the owner.

## Write the insights

Format each as: **finding, evidence, so what.**

:::example Insight written well
**Electronics is a small part of the orders but most of the money.** Electronics made up about one fifth of orders (21%) but about three quarters of revenue (76%), because the average electronics order (about 24,600 rupees) is roughly 26 times a grocery order (about 950 rupees). Protecting electronics stock and service matters more than any other category.
:::

:::example An insight with a limit
**Discounted orders do not appear to be larger.** Discounted orders were only slightly larger (3.03 units against 2.88) and brought in less money per order (about 6,400 rupees against 6,900), so the data does not show that discounts make customers buy enough more to pay for themselves. This is only a comparison of past orders, not an experiment, so it cannot prove cause. A small test (offer a discount in one city for a month) would answer it properly.
:::

Notice the honesty. A claim you cannot prove should be written as "the data suggests", with the limit stated.

## Write recommendations

A good recommendation has an **action**, a **reason** and, if possible, an **expected effect** or a way to measure it.

| Weak | Strong |
| --- | --- |
| "Sell more electronics." | "Keep electronics stocked at all four shops and train staff to upsell accessories; electronics is about three quarters of revenue." |
| "Discounts are bad." | "Test a 10% discount in one city for four weeks and compare average quantity with the other cities before deciding on offers." |
| "Improve Salem." | "Salem has the smallest revenue share; before investing, check its footfall and stock availability, since orders there are as large as elsewhere." |

## A structure for the findings page

| Section | Content |
| --- | --- |
| **Headline** | the single most important finding, in one sentence |
| **Key numbers** | 3 to 5 numbers: revenue, orders, average order value |
| **Findings** | 3 insights, each with a chart or table |
| **Limits** | what the data cannot tell us |
| **Recommendations** | 2 or 3 actions, in priority order |
| **Next steps** | what data would improve the analysis (costs for profit, customer ids for repeat purchases) |

## Mistakes to avoid

| Mistake | Better |
| --- | --- |
| listing every number you found | choose the **three** that matter |
| claiming cause from a comparison | say "associated with", and propose a test |
| hiding limits | state them: it builds trust |
| jargon (IQR, groupby) in the report for the owner | plain words |
| a recommendation the owner cannot act on | name a concrete action |
| changing the story to fit what the owner hopes | report what the data says |

:::remember
The test of a good analysis: if the owner reads only the first paragraph, do they know what to do?
:::
