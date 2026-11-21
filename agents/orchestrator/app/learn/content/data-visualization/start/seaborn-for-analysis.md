---
title: Seaborn for analysis
summary: Draw statistical charts in one line with Seaborn: distributions, box plots, scatter plots by group, heat maps and pair plots.
takeaways:
- Seaborn sits on top of Matplotlib and works directly with DataFrames
- Use histplot and boxplot for spread, scatterplot with hue for groups, heatmap for correlations
- One line gives a chart that would take many lines in plain Matplotlib
---
## Why Seaborn

Seaborn is built on Matplotlib. You give it a **DataFrame** and column names, and it makes good-looking statistical charts with sensible defaults.

```py
import seaborn as sns
sns.set_theme(style="whitegrid")
```

We will use the famous iris flower data that comes with scikit-learn:

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from sklearn.datasets import load_iris

sns.set_theme(style="whitegrid")
iris = load_iris(as_frame=True)
df = iris.frame.rename(columns={"sepal length (cm)": "sepal_length", "sepal width (cm)": "sepal_width",
                                "petal length (cm)": "petal_length", "petal width (cm)": "petal_width"})
df["species"] = df["target"].map(dict(enumerate(iris.target_names)))
df = df.drop(columns="target")

print(df.shape)
print(df.head(3))
print(df["species"].value_counts().to_string())
```

```output
(150, 5)
   sepal_length  sepal_width  petal_length  petal_width species
0           5.1          3.5           1.4          0.2  setosa
1           4.9          3.0           1.4          0.2  setosa
2           4.7          3.2           1.3          0.2  setosa
species
setosa        50
versicolor    50
virginica     50
```

## Distributions: histogram and box plot

```python
fig, axes = plt.subplots(1, 2, figsize=(11, 4))

sns.histplot(data=df, x="petal_length", hue="species", bins=20, ax=axes[0])
axes[0].set_title("Petal length by species")

sns.boxplot(data=df, x="species", y="petal_length", ax=axes[1])
axes[1].set_title("Petal length: the box is the middle half")

print("histogram groups:", [t.get_text() for t in axes[0].get_legend().get_texts()])
print("box plot categories:", [t.get_text() for t in axes[1].get_xticklabels()])
```

```output
histogram groups: ['setosa', 'versicolor', 'virginica']
box plot categories: ['setosa', 'versicolor', 'virginica']
```

How to read a **box plot**: the box covers the middle 50% of values (Q1 to Q3), the line inside is the median, the whiskers reach the typical range, and dots beyond the whiskers are potential outliers.

The numbers behind the box plot:

```python
print(df.groupby("species")["petal_length"].describe()[["mean", "min", "25%", "50%", "75%", "max"]].round(2).to_string())
```

```output
            mean  min  25%   50%   75%  max
species
setosa      1.46  1.0  1.4  1.50  1.58  1.9
versicolor  4.26  3.0  4.0  4.35  4.60  5.1
virginica   5.55  4.5  5.1  5.55  5.88  6.9
```

Setosa is completely separate (petal length 1.0 to 1.9), while versicolor (3.0 to 5.1) and virginica (4.5 to 6.9) overlap only a little. One look at the chart (or this table) tells you petal length separates the species well.

## Relationships: scatter plot with a colour for groups

```python
fig, ax = plt.subplots(figsize=(6, 4.5))
sns.scatterplot(data=df, x="petal_length", y="petal_width", hue="species", ax=ax)
ax.set_title("Petals: three clear groups")

print("groups drawn:", len(ax.get_legend().get_texts()))
print("points drawn:", sum(len(c.get_offsets()) for c in ax.collections))
```

```output
groups drawn: 3
points drawn: 150
```

Adding `hue="species"` colours the dots by group, so a third variable appears with no extra effort.

## Correlation heat map

```python
corr = df.drop(columns="species").corr().round(2)
fig, ax = plt.subplots(figsize=(5, 4))
sns.heatmap(corr, annot=True, cmap="Blues", vmin=-1, vmax=1, ax=ax)
ax.set_title("Which measurements move together?")

print(corr.to_string())
```

```output
              sepal_length  sepal_width  petal_length  petal_width
sepal_length          1.00        -0.12          0.87         0.82
sepal_width          -0.12         1.00         -0.43        -0.37
petal_length          0.87        -0.43          1.00         0.96
petal_width           0.82        -0.37          0.96         1.00
```

A heat map turns a table of correlations into colours: dark squares mean a strong link. Here petal length and petal width are almost perfectly linked (about 0.96), so a model does not need both.

## Many charts at once: the pair plot

```py
sns.pairplot(df, hue="species")        # every pair of columns, in one grid
plt.show()
```

One line draws a grid of scatter plots for every pair of columns, with the species coloured. It is a favourite first look at any new dataset.

## Which Seaborn chart for which question

| Question | Chart |
| --- | --- |
| how is one number spread? | `histplot`, `kdeplot`, `boxplot` |
| how do groups compare? | `boxplot`, `barplot`, `violinplot` |
| are two numbers related? | `scatterplot`, `regplot` (adds a trend line) |
| which columns are linked? | `heatmap` of `df.corr()` |
| how many in each category? | `countplot` |
| everything at once | `pairplot` |

:::warning
A heat map of correlations only measures **straight-line** links, and "linked" never means "causes". A strong correlation can also come from a hidden third factor.
:::
