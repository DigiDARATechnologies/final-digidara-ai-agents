---
title: What is data science?
summary: Data science turns raw data into decisions. Learn the workflow, the roles and the tools, with a first small example.
takeaways:
- Data science answers questions with data, using statistics, programming and domain knowledge
- Every project follows the same workflow: ask, collect, clean, explore, model, communicate
- Most of the time goes into cleaning and understanding data, not modelling
---
## Questions, answered with data

A shop owner asks, "Which products should I stock more of?" A hospital asks, "Which patients are likely to return within a month?" A college asks, "Which students need extra help?" **Data science** is the craft of answering questions like these using data.

It sits where three skills meet:

| Skill | What it gives |
| --- | --- |
| **Programming** | Python, SQL: getting and shaping the data |
| **Statistics and maths** | knowing what the numbers really tell you |
| **Domain knowledge** | knowing which questions matter and which answers make sense |

## The workflow

| Step | What you do | Tools |
| --- | --- | --- |
| 1. **Ask** | turn a business problem into a question with a measurable answer | conversation, notes |
| 2. **Collect** | get the data: files, databases, APIs | SQL, Pandas |
| 3. **Clean** | fix missing values, errors, duplicates | Pandas, NumPy |
| 4. **Explore** | look at distributions and relationships | Pandas, charts |
| 5. **Model** | find patterns or build predictions | scikit-learn |
| 6. **Communicate** | explain the result so someone can act on it | charts, reports |

Real projects loop back: a surprise in step 4 sends you back to step 3. Experienced data scientists say 60 to 80% of their time goes to steps 2 to 4.

## Roles

| Role | Focus |
| --- | --- |
| **Data analyst** | reports, dashboards and answers from existing data (SQL, Excel, Pandas, charts) |
| **Data scientist** | analysis plus statistical and machine learning models |
| **Machine learning engineer** | putting models into working products |
| **Data engineer** | building the pipelines that deliver clean data |

## A first taste

scikit-learn includes a real dataset of 178 wines tested in a lab. Here is a data science question: *do the three types of wine differ in alcohol?*

```python
import pandas as pd
from sklearn.datasets import load_wine

wine = load_wine(as_frame=True).frame
wine["type"] = wine["target"].map({0: "class_0", 1: "class_1", 2: "class_2"})
print(wine.shape)
print(wine.groupby("type")["alcohol"].mean().round(2))
```

```output
(178, 15)
type
class_0    13.74
class_1    12.28
class_2    13.15
Name: alcohol, dtype: float64
```

One short table already gives an answer: one wine type has clearly higher alcohol than another. The rest of this course shows how to **trust** an answer like that, and how to find it for your own data.

:::note
You do not need advanced maths to start. You need curiosity, careful thinking, and the habit of asking "does this number really prove that?"
:::

:::tip
Practise on real data: Kaggle, data.gov.in and the UCI repository have free datasets. The best way to learn is to pick one that interests you and answer a question about it.
:::
