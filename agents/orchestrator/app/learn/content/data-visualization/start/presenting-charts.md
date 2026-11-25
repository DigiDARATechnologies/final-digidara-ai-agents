---
title: Choosing and presenting charts
summary: Pick the right chart for each question, avoid misleading charts, and make a short, clear data story for other people.
takeaways:
- Choose the chart from the question: trend, comparison, share, distribution or relationship
- Honest charts start at zero for bars, label units and avoid decoration
- A good data story has a headline, one chart per point and a clear recommendation
---
## Choose the chart from the question

| You want to show | Best chart | Avoid |
| --- | --- | --- |
| a **trend** over time | line chart | pie chart |
| a **comparison** between groups | sorted bar chart | 3-D bars |
| a **share** of a whole (4 parts or fewer) | bar chart of percentages, or a pie | a pie with many slices |
| how a number is **spread** | histogram, box plot | a table of raw values |
| a **relationship** between two numbers | scatter plot | a line chart |
| **two dimensions** together | heat map, grouped bars | too many colours |

## Honest charts

A chart can mislead without any false number. See the effect of the axis:

```python
import numpy as np

before, after = 92, 95
print("true change:", f"{100 * (after - before) / before:.1f}%")

# a bar chart whose axis starts at 90 makes the second bar look much taller
axis_start = 90
shown_ratio = (after - axis_start) / (before - axis_start)
print("bar height ratio when the axis starts at 90:", round(shown_ratio, 2), "times as tall")
print("bar height ratio when the axis starts at 0 :", round(after / before, 2), "times as tall")
```

```output
true change: 3.3%
bar height ratio when the axis starts at 90: 2.5 times as tall
bar height ratio when the axis starts at 0 : 1.03 times as tall
```

The marks rose by about 3%, but a bar chart with an axis starting at 90 makes the second bar look **two and a half times** as tall. Always start **bar** charts at zero. (Line charts may start higher when the goal is to show change, but label the axis clearly.)

| Misleading habit | Honest alternative |
| --- | --- |
| a cut-off axis on a bar chart | start at zero |
| 3-D effects and shadows | flat, simple shapes |
| a rainbow of colours | one colour, one highlight |
| unlabelled axes | label axes and units |
| a pie chart of many slices | a sorted bar chart |
| picking a time range that hides a drop | show the full period |

## Colour that helps

- Use **one main colour** for the data and a **second colour** for the single thing you want people to notice.
- Make sure the chart works for people with colour blindness: avoid red against green alone; add labels or patterns.
- Keep enough **contrast**; light grey on white is hard to read on a projector.

## The data story

Numbers convince people when they come as a **story**:

| Step | What to write |
| --- | --- |
| **1. Headline** | the conclusion in one sentence: "Chennai brings 40% of revenue" |
| **2. Evidence** | one chart for each supporting point, with a title that states the message |
| **3. Context** | compared with what? last year, the target, the average |
| **4. Limits** | what the data cannot tell you |
| **5. Recommendation** | what to do next, in concrete terms |

:::example Weak and strong titles
**Weak:** "Sales by month"
**Strong:** "Sales peaked in December at 5.2 lakh, almost double the June low"
:::

## Present in the tools people use

| Tool | When |
| --- | --- |
| **Jupyter notebook** | share your analysis with technical people |
| **PowerPoint or Google Slides** | present to managers: paste charts saved with `savefig` |
| **Streamlit** | turn the analysis into a small interactive web page |
| **Power BI or Tableau** | build dashboards that business users can filter |

A tiny Streamlit dashboard:

```py
import pandas as pd
import streamlit as st

df = pd.read_csv("sales_clean.csv")
city = st.selectbox("City", sorted(df["city"].unique()))
view = df[df["city"] == city]
st.metric("Revenue", f"{view['revenue'].sum():,.0f}")
st.bar_chart(view.groupby("category")["revenue"].sum())
```

## Checklist before you share a chart

| Check | |
| --- | --- |
| Does the title state the message? | |
| Are axes labelled with units? | |
| Do bar charts start at zero? | |
| Is the chart readable from the back of the room? | |
| Could someone misread it? | |
| Is there a source and a date? | |

:::practice capstone-project
Show one of your charts to the Capstone Project agent and ask which part a first-time reader would misread.
:::
