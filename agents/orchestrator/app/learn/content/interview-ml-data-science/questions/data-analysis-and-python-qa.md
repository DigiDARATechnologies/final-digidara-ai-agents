---
title: Data analysis and Python for data questions
summary: Pandas, NumPy, SQL for analysts, data cleaning, and how to discuss a data project.
kind: qa
takeaways:
- Be fluent with pandas operations interviewers test
- Explain how you clean data and handle outliers
- Tell a clear story for your data project
---
### Q [Easy] NumPy array vs Python list?
A NumPy array holds items of one type in contiguous memory and supports fast vectorised operations; a list can mix types but is slower for numerical work.

### Q [Easy] Series vs DataFrame in pandas?
A **Series** is a one-dimensional labelled array. A **DataFrame** is a two-dimensional table of Series sharing an index.

### Q [Medium] How do you find and drop duplicates and missing values?
```python
df.duplicated().sum()
df = df.drop_duplicates()
df.isna().sum()
df = df.dropna(subset=["email"])
df["age"] = df["age"].fillna(df["age"].median())
```

### Q [Medium] `loc` vs `iloc`?
`loc` selects by **label** (inclusive of the end label). `iloc` selects by **integer position** (the end is excluded).

### Q [Medium] How do you group and aggregate?
```python
df.groupby("city")["sales"].agg(["sum", "mean", "count"])
```

### Q [Medium] merge vs join vs concat in pandas?
`merge` combines tables on columns (like SQL joins). `join` combines on the index. `concat` stacks DataFrames along rows or columns.

### Q [Medium] How do you detect outliers?
Using the **IQR rule** (values below Q1 - 1.5 x IQR or above Q3 + 1.5 x IQR), z-scores (beyond 3 standard deviations), or box plots. Decide whether to remove, cap or keep them after understanding why they occur.

### Q [Medium] What is apply and why is it sometimes slow?
`apply` runs a Python function row by row or column by column. It is slower than **vectorised** operations (`df["a"] + df["b"]`) because it does not use optimised compiled code.

### Q [Medium] How do you handle a dataset too large for memory?
Read in **chunks** (`chunksize`), choose smaller data types, load only needed columns, use a database or tools like Dask or Spark.

### Q [Medium] Write a SQL query for the top 3 products by sales in each category.
```sql
SELECT *
FROM (
    SELECT category, product, sales,
           ROW_NUMBER() OVER (PARTITION BY category ORDER BY sales DESC) AS rn
    FROM products
) ranked
WHERE rn <= 3;
```

### Q [Medium] How do you choose a chart type?
Comparison across categories: bar. Trend over time: line. Share of a whole (few parts): pie or stacked bar. Relationship between two numbers: scatter. Distribution: histogram or box plot.

### Q [Hard] Walk me through a data analysis project.
Use a clear structure: **problem** (the business question), **data** (source, size, quality issues), **cleaning** (what you fixed and why), **analysis** (key methods), **findings** (two or three insights with numbers), **recommendation** (what to do), and **limits** (what you would improve). Quote one number that shows impact.

### Q [Hard] Your model is accurate in testing but poor in production. Why?
Likely causes: **data leakage**, a test set that does not reflect real data, **data drift** (the live data changed), differences between training and serving preprocessing, or imbalance. Fix by checking the pipeline, monitoring inputs and retraining on fresh data.
