---
title: Present and publish your analysis
summary: Package the work for others: a notebook or report, a clean repository, a short presentation, and how to describe the project on your resume and in interviews.
takeaways:
- Deliver the answer first, the method second
- A tidy repository and notebook show that you work professionally
- Be ready to explain every cleaning decision and every number
---
## Package the work

You have questions, a cleaned dataset, tables, charts and recommendations. How you **deliver** them decides whether anyone uses them.

| Audience | Best format |
| --- | --- |
| the shop owner | a short **PDF or slide deck**: headline, three charts, recommendations |
| a technical reviewer or recruiter | a **Jupyter notebook** or GitHub repository with the code and explanation |
| ongoing use | a **dashboard** (Power BI, Tableau, Streamlit) that updates |

## The notebook

A Jupyter notebook mixes code, results and text. Structure it like a report:

| Section | Content |
| --- | --- |
| **Title and summary** | the business question and the main answer, at the top |
| **Data** | where it came from, what it contains, what is wrong with it |
| **Cleaning** | each step with before and after counts |
| **Analysis** | one section per question, with a table or chart and a sentence of interpretation |
| **Recommendations and limits** | what to do, and what the data cannot say |
| **Appendix** | extra tables, the definition of each measure |

Tips for readable notebooks:

- Write a **markdown sentence above every chart** saying what to look for.
- **Restart and run all** before you save, to prove that it works from top to bottom.
- Keep **long code in functions** (or a `.py` file) so the notebook reads like a story.
- Do not leave error messages, debugging prints or empty cells.

## The repository

```py
retail-sales-analysis/
  README.md
  requirements.txt
  data/
    sales_raw.csv          # untouched
    sales_clean.csv        # produced by the code
  notebooks/
    analysis.ipynb
  src/
    clean.py               # cleaning functions
  reports/
    sales_overview.png
    findings.pdf
```

A good README for this project:

```py
# Retail Sales Analysis (2025)

**Question:** Where does a four-city retail business make money, and what should it focus on next year?

**Answer in one line:** Electronics drives about three quarters of revenue from one fifth of orders; Chennai is the largest city.

## What I did
1. Cleaned 605 raw order rows (5 duplicates, 3 impossible quantities, inconsistent city names, missing cities).
2. Analysed revenue by month, city and category, and compared discounted with full-price orders.
3. Wrote recommendations and listed the limits of the data.

## Tools
Python, pandas, matplotlib, Jupyter.

## Key charts
![Overview](reports/sales_overview.png)

## How to run
    pip install -r requirements.txt
    jupyter notebook notebooks/analysis.ipynb

## Limits and next steps
No cost data, so profit is unknown; no customer ids, so repeat purchases cannot be measured.
```

## Present it in five minutes

| Slide | Content |
| --- | --- |
| 1. Question | what the owner asked, in plain words |
| 2. Headline | "Electronics brings about three quarters of revenue from a fifth of orders." |
| 3. Evidence | the one chart that proves it |
| 4. Other findings | city and discounts, one slide each |
| 5. Recommendations | 2 or 3 actions, who and when |
| 6. Limits and next steps | what you would do with more data |

Speak to the **decision**, not the code. Keep the technical details for questions.

## A dashboard (next step)

Turn the analysis into something people can use. With **Streamlit** you can make a small web app from the same pandas code:

```py
# app.py   (run with: streamlit run app.py)
import pandas as pd
import streamlit as st

df = pd.read_csv("sales_clean.csv", parse_dates=["order_date"])
st.title("Retail sales dashboard")

city = st.sidebar.multiselect("City", sorted(df["city"].unique()), default=sorted(df["city"].unique()))
view = df[df["city"].isin(city)]

col1, col2, col3 = st.columns(3)
col1.metric("Revenue", f"{view['revenue'].sum():,.0f}")
col2.metric("Orders", len(view))
col3.metric("Average order", f"{view['revenue'].mean():,.0f}")

st.bar_chart(view.groupby("category")["revenue"].sum())
st.line_chart(view.groupby("month")["revenue"].sum())
```

Power BI or Tableau achieve the same with drag and drop, and are the tools most companies use.

## On your resume

:::example Resume entry
**Retail Sales Analysis** (Python, pandas, matplotlib, SQL)
- Cleaned and analysed 600+ order records (duplicates, missing values, inconsistent text, invalid quantities) and documented each decision.
- Found that electronics generated about three quarters of revenue from one fifth of orders, and that discounts did not clearly raise order sizes; recommended a controlled discount test.
- Delivered a notebook, five-minute presentation and Streamlit dashboard. GitHub: github.com/yourname/retail-sales-analysis
:::

Notice the pattern: **what you did, what you found, what it led to.**

## Interview questions about this project

| Question | Prepare |
| --- | --- |
| "Walk me through the project." | question, data, cleaning, finding, recommendation (60 seconds) |
| "Why did you fill missing cities with Unknown instead of dropping them?" | dropping would understate revenue; they were real orders |
| "How do you know your cleaning did not hide a problem?" | the before and after counts and the checks |
| "Is revenue the right measure?" | profit needs cost data; mention margin |
| "Could the discount finding be wrong?" | yes: observational data, no experiment; I proposed a test |
| "What would you do with more time?" | cost data, customer ids, forecasting, a dashboard |
| "What was the hardest part?" | a real story (cleaning, choosing a measure, explaining to a non-technical person) |

## Use your own data next

This project used a practice dataset so that you can repeat it exactly. To stand out, repeat the **method** on real data about something you care about:

| Data source | Ideas |
| --- | --- |
| **Kaggle** (kaggle.com/datasets) | thousands of free datasets: sales, sports, health, education |
| **data.gov.in** | Indian government open data: agriculture, transport, census, rainfall |
| **Your college or club** | attendance, results, event feedback (anonymise it) |
| **Public APIs** | weather, cricket scores, exchange rates |
| **Your own life** | expenses, study hours, fitness, reading |

The method stays the same: **frame the question, clean the data, analyse, visualise, recommend, present.**

:::practice capstone-project
Pick a real dataset, share your list of business questions with the Capstone Project agent, and ask whether each question can really be answered with that data.
:::
