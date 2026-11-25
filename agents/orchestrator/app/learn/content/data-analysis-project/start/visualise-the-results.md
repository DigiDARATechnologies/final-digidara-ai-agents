---
title: Visualise the results
summary: Turn the tables into clear charts: choose the right chart for each question, build text charts you can read in the terminal, and write matplotlib code for real figures.
takeaways:
- Pick the chart by the question: trend (line), comparison (bars), share (a few slices or bars)
- A good chart has a message as its title, labelled axes, and no clutter
- Check the chart against the numbers before you share it
---
## Choose the chart for the question

| Question | Chart | Why |
| --- | --- | --- |
| How did sales change month by month? | **line chart** | shows a trend over time |
| Which city or category is biggest? | **bar chart** (sorted) | easy to compare lengths |
| What share does each part take? | **bar chart** of percentages (or a pie with 4 slices or fewer) | pies are hard to compare when there are many parts |
| How are order values spread? | **histogram** | shows the distribution |
| City by category together | **grouped or stacked bars**, or a heat map | two dimensions |

## A quick chart without any library

Before we draw real figures, you can test an idea with a text chart. It also proves the numbers.

```python
import pandas as pd

df = pd.read_csv("sales_clean.csv", parse_dates=["order_date"])

def text_bars(series, width=40, unit=1000):
    biggest = series.max()
    for label, value in series.items():
        bar = "#" * int(round(width * value / biggest))
        print(f"{str(label):<12} {bar:<{width}} {value / unit:>8,.0f}k")

by_city = df.groupby("city")["revenue"].sum().sort_values(ascending=False)
print("Revenue by city (thousands of rupees)")
text_bars(by_city)
```

```output
Revenue by city (thousands of rupees)
Chennai      ########################################    1,587k
Coimbatore   ##########################                  1,031k
Madurai      ##################                            730k
Salem        ##############                                562k
Unknown      #                                              54k
```

You can read it at a glance: the longest bar is the biggest city. Sorting the bars from largest to smallest is the first rule of a good bar chart.

```python
by_category = df.groupby("category")["revenue"].sum().sort_values(ascending=False)
print("Revenue by category (thousands of rupees)")
text_bars(by_category)

monthly = df.groupby("month")["revenue"].sum()
print("\nRevenue by month (thousands of rupees)")
text_bars(monthly, width=30)
```

```output
Revenue by category (thousands of rupees)
Electronics  ########################################    3,023k
Clothing     ########                                      625k
Groceries    ##                                            185k
Books        ##                                            133k

Revenue by month (thousands of rupees)
2025-01      ##############                      247k
2025-02      ####################                349k
2025-03      #############################       507k
2025-04      ####################                346k
2025-05      ###########                         194k
2025-06      #####                                80k
2025-07      #######################             393k
2025-08      ##################                  313k
2025-09      #########################           432k
2025-10      ####################                346k
2025-11      ##############                      243k
2025-12      ##############################      516k
```

## Real charts with matplotlib

Install the library with `pip install matplotlib`. Then:

```py
import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))

# 1. line chart: the monthly trend
monthly = df.groupby("month")["revenue"].sum() / 1000
axes[0].plot(monthly.index, monthly.values, marker="o", color="#2563eb")
axes[0].set_title("Monthly revenue (thousand rupees)")
axes[0].tick_params(axis="x", rotation=60)

# 2. horizontal bars: revenue by city, sorted
city = df.groupby("city")["revenue"].sum().sort_values() / 1000
axes[1].barh(city.index, city.values, color="#16a34a")
axes[1].set_title("Revenue by city (thousand rupees)")

# 3. bars: revenue by category, sorted
category = df.groupby("category")["revenue"].sum().sort_values(ascending=False) / 1000
axes[2].bar(category.index, category.values, color="#f59e0b")
axes[2].set_title("Revenue by category (thousand rupees)")

for ax in axes:
    ax.spines[["top", "right"]].set_visible(False)       # remove clutter

plt.tight_layout()
plt.savefig("sales_overview.png", dpi=150)               # save an image to share
plt.show()
```

## The rules of a good chart

| Rule | Detail |
| --- | --- |
| **the title states the message** | "Chennai brings in 40% of revenue", not "Revenue by city" |
| **label axes and units** | thousands of rupees, number of orders |
| **sort bars** | largest to smallest (except for months and other natural orders) |
| **start bar charts at zero** | otherwise small differences look huge |
| **few colours, with purpose** | one colour for the data; a highlight colour for the point you want to make |
| **remove clutter** | gridlines, borders, 3-D effects, rainbow colours |
| **do not use a pie chart** for more than 4 or 5 parts | slices are hard to compare |
| **make it readable** | font size large enough for a presentation |

:::example Weak and strong chart titles
**Weak:** "Sales by month"
**Strong:** "Sales peaked in October at ₹4.2 lakh, almost double the February low"

The strong title tells the reader what to notice before they study the chart.
:::

## Check the picture against the numbers

A chart can mislead without any false number. Before sharing, ask:

| Check | |
| --- | --- |
| Does the tallest bar match the largest number in the table? | |
| Does the axis start at zero for bars? | |
| Is the time order correct (January to December)? | |
| Are the units written? | |
| Would someone who did not see my table draw the same conclusion? | |

```python
print("city with the longest bar :", by_city.idxmax())
print("its value in the table    :", f"{by_city.max():,.0f}")
print("cities add up to the total:", round(by_city.sum(), 2) == round(df["revenue"].sum(), 2))
```

```output
city with the longest bar : Chennai
its value in the table    : 1,587,397
cities add up to the total: True
```

## Tools beyond matplotlib

| Tool | Good for |
| --- | --- |
| **seaborn** | nicer statistical charts with less code |
| **Plotly** | interactive charts (hover, zoom) for web pages |
| **Power BI, Tableau** | drag-and-drop dashboards (very common in jobs) |
| **Excel** | quick charts and pivot tables for business users |
| **Streamlit** | turn your analysis into a small interactive web app |

:::practice capstone-project
Show your three charts to the Capstone Project agent and ask which chart title or axis would confuse a first-time reader.
:::
