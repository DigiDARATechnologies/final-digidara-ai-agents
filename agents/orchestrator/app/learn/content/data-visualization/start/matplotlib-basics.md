---
title: Matplotlib basics
summary: Draw line, bar, scatter and histogram charts with Matplotlib, label them properly, and save them as images.
takeaways:
- Matplotlib draws on a figure that holds one or more axes (the plots)
- The four charts to know: line, bar, scatter and histogram
- Always add a title, axis labels and units, and save with savefig
---
## Why visualise

Numbers in a table hide patterns. A chart shows a trend, a gap or an outlier in a second. Data scientists draw charts at every step: exploring data, checking a model, and explaining results.

```py
pip install matplotlib seaborn
```

## Figure and axes

A **figure** is the whole picture. **Axes** is one plot inside it. The usual pattern:

```python
import matplotlib
matplotlib.use("Agg")                      # draw without a screen window, so this runs anywhere
import matplotlib.pyplot as plt

months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
sales = [120, 135, 128, 160, 172, 190]

fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(months, sales, marker="o", color="#2563eb")
ax.set_title("Monthly sales rose through the half year")
ax.set_xlabel("Month")
ax.set_ylabel("Sales (thousand rupees)")
ax.grid(alpha=0.3)

print("title :", ax.get_title())
print("x axis:", ax.get_xlabel(), "| y axis:", ax.get_ylabel())
print("points drawn:", len(ax.lines[0].get_ydata()))
```

```output
title : Monthly sales rose through the half year
x axis: Month | y axis: Sales (thousand rupees)
points drawn: 6
```

In a notebook or a script on your own computer, finish with `plt.show()` to see the picture, or `fig.savefig("sales.png", dpi=150)` to save it. Here we print what was drawn, because a book cannot display your window.

## The four charts to know

| Chart | Use it to | Code |
| --- | --- | --- |
| **Line** | show a trend over time | `ax.plot(x, y)` |
| **Bar** | compare categories | `ax.bar(names, values)` |
| **Scatter** | see the relationship between two numbers | `ax.scatter(x, y)` |
| **Histogram** | see how one number is spread | `ax.hist(values, bins=10)` |

```python
import numpy as np

rng = np.random.default_rng(0)
hours = rng.uniform(1, 8, 60)
marks = 35 + 7 * hours + rng.normal(0, 6, 60)
cities = ["Chennai", "Madurai", "Salem", "Coimbatore"]
revenue = [158, 103, 73, 56]

fig, axes = plt.subplots(1, 3, figsize=(14, 4))

axes[0].bar(cities, revenue, color="#16a34a")
axes[0].set_title("Revenue by city (lakh rupees)")

axes[1].scatter(hours, marks, alpha=0.7)
axes[1].set_title("More study hours, higher marks")
axes[1].set_xlabel("Study hours")
axes[1].set_ylabel("Marks")

axes[2].hist(marks, bins=8, color="#f59e0b", edgecolor="white")
axes[2].set_title("How marks are spread")
axes[2].set_xlabel("Marks")

print("bars drawn      :", len(axes[0].patches))
print("scatter points  :", len(axes[1].collections[0].get_offsets()))
print("histogram bars  :", len(axes[2].patches))
print("correlation of the scatter:", round(float(np.corrcoef(hours, marks)[0, 1]), 2))
```

```output
bars drawn      : 4
scatter points  : 60
histogram bars  : 8
correlation of the scatter: 0.92
```

The scatter's correlation is high and positive, which is why the dots form a rising band.

## A text view of a histogram

You can also check a distribution without a picture by counting values per bin:

```python
counts, edges = np.histogram(marks, bins=6)
for count, low, high in zip(counts, edges[:-1], edges[1:]):
    print(f"{low:5.1f} to {high:5.1f} | {'#' * int(count)}")
```

```output
 32.6 to  43.5 | ####
 43.5 to  54.4 | ###########
 54.4 to  65.2 | #########
 65.2 to  76.1 | #################
 76.1 to  87.0 | ###############
 87.0 to  97.8 | ####
```

This is exactly the information a histogram draws as bars.

## Save the chart

```python
import io

buffer = io.BytesIO()
fig.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
print("image saved, size over 5 KB:", buffer.tell() > 5_000)
```

```output
image saved, size over 5 KB: True
```

With a real file: `fig.savefig("overview.png", dpi=150, bbox_inches="tight")`. Use `dpi=150` or more for slides and reports.

## Habits of a clear chart

| Habit | Why |
| --- | --- |
| a **title** that states the message | the reader knows what to notice |
| **axis labels with units** | numbers need meaning |
| start **bar** charts at zero | otherwise small differences look huge |
| few colours, used on purpose | colour should guide, not decorate |
| remove clutter (extra borders, 3-D, heavy grids) | focus on the data |

:::tip
Matplotlib has two styles: the quick `plt.plot(...)` and the explicit `fig, ax = plt.subplots()`. Use the explicit one from the start. It scales to several charts and is what most professional code uses.
:::
