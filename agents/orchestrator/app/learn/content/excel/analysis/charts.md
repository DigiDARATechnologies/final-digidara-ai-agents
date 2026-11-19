---
title: Charts and dashboards
summary: Choose the right chart for the question, build and clean it up, and combine charts, pivots and slicers into a simple dashboard.
takeaways:
- Choose the chart by the question: comparison, trend, share or relationship
- Clean charts beat decorated ones: clear title, honest axis, no clutter
- A dashboard is a handful of linked charts and numbers on one screen
---
## Choose by the question

| Question | Use | Avoid |
| --- | --- | --- |
| Compare categories (sales by region) | **column** or **bar** chart | pie with many slices |
| Trend over time | **line** chart | a column chart for hundreds of days |
| Share of a whole (only a few parts) | **pie or doughnut** (at most 4 or 5 slices) | pie for exact comparison |
| Relationship between two numbers | **scatter** (XY) | line chart |
| Distribution of values | **histogram** | column chart of raw values |
| Progress to a target | bar with a target line, or a bullet chart | 3-D charts |
| Two measures with different scales | **combo** chart with a secondary axis | too many series |

Never use 3-D effects: they distort the sizes you are trying to show.

## Build a chart

1. Select the data **including the headers**.
2. **Insert**, then pick the chart (or **Recommended Charts**).
3. Use the **Chart Design** and **Format** tabs, or the three buttons at the chart's corner (**Elements**, **Styles**, **Filters**).

| Element | Tips |
| --- | --- |
| **Title** | say the point: "Sales rose 20% in March", not "Chart 1" |
| **Axis** | start bar and column charts at **zero**; a truncated axis exaggerates differences |
| **Gridlines** | light grey, or remove them |
| **Data labels** | show exact values when there are few bars; remove clutter when there are many |
| **Legend** | remove it if there is only one series |
| **Colours** | one colour for one series; use a highlight colour for the bar that matters |

:::warning
A chart can mislead without any false number: a bar chart axis that starts at 90 makes a change from 92 to 95 look huge. Keep the axis honest, and label units.
:::

## Charts that update themselves

If the source is an Excel **Table** (or a PivotTable), the chart grows as rows are added. For a chart of the "last 12 months", use a Table plus a formula-driven range, or a PivotChart with a timeline slicer.

The numbers a chart summarises can themselves be prepared with formulas. Here is a monthly series and a three-month moving average that smooths the noise:



The three-month moving averages are **103.3, 120, 123.3 and 150**, and sales grew **70%** from the first month to the last (100 to 170). Plot the raw series and the moving average on one line chart to show the trend behind the ups and downs.

## Combo charts and secondary axes

When one series is revenue (lakhs) and another is a percentage margin, plotting them on the same axis flattens the smaller one. Select the chart, **Change Chart Type, Combo**, make revenue a **column** and margin a **line on the secondary axis**. Keep these to two series.

## Sparklines

**Insert, Sparklines (Line, Column, Win/Loss)** puts a tiny chart **inside a single cell**, perfect for showing each salesperson's monthly trend beside their name, without a full chart.

## A simple dashboard

A dashboard is not decoration: it answers a few questions on **one screen**.

| Part | How |
| --- | --- |
| headline numbers (total sales, orders, average) | formulas in big, bold cells (`SUM`, `COUNT`, `AVERAGE`) |
| 3 or 4 charts | from PivotTables (one pivot per chart) |
| filters | **Slicers** and a **Timeline**, connected to all the pivots (Report Connections) |
| layout | a separate sheet, gridlines off, aligned boxes, a consistent colour palette |

Steps: build each pivot on a "Data" sheet, make the charts, cut and paste them to a "Dashboard" sheet, add slicers and connect them to every pivot, then hide the working sheets or protect them.

:::tip
Ask "what decision will this help?" before building. Remove any chart that does not answer a question the reader has. Three clear charts beat ten busy ones.
:::
