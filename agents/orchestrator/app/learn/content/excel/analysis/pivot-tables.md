---
title: Pivot tables
summary: Summarise thousands of rows in seconds: build a PivotTable, group dates, add calculated values, slicers and a pivot chart.
takeaways:
- A PivotTable summarises data by dragging fields, with no formulas
- Rows and Columns group the data; Values calculate (sum, count, average)
- Refresh after the data changes; start from a clean Table
---
## What a PivotTable does

Imagine 5,000 sales rows (date, region, product, quantity, amount) and the question "What was the total amount for each region and product?" With formulas you would write dozens of `SUMIFS`. A **PivotTable** answers it by dragging fields, in seconds, and lets you change your mind just as quickly.

## Prepare the data

A PivotTable needs **tidy data**: one header row, one record per row, no blank rows, no merged cells, no subtotals mixed in. Best practice: convert the data to a **Table** (`Ctrl + T`) so the pivot grows with it.

| Region | Product | Qty | Amount |
| --- | --- | --- | --- |
| North | Pen | 10 | 100 |
| South | Pen | 5 | 50 |
| North | Book | 2 | 240 |
| South | Book | 3 | 360 |
| North | Pen | 20 | 200 |
| South | Pen | 15 | 150 |

## Build one

1. Click inside the data (or Table).
2. **Insert, PivotTable.** Put it on a new worksheet.
3. In the field list, drag fields into four areas:

| Area | Purpose | Example |
| --- | --- | --- |
| **Rows** | what goes down the side | Region |
| **Columns** | what goes across the top | Product |
| **Values** | what to calculate | Sum of Amount |
| **Filters** | a filter for the whole pivot | Year |

With Region in Rows, Product in Columns and Sum of Amount in Values, the result for the table above is:

| | Book | Pen | Grand Total |
| --- | --- | --- | --- |
| **North** | 240 | 300 | 540 |
| **South** | 360 | 200 | 560 |
| **Grand Total** | 600 | 500 | 1100 |

You can confirm those numbers with the formulas a pivot replaces:



## Changing the calculation

Right-click a value, then **Summarize Values By**: Sum, Count, Average, Max, Min. **Show Values As** gives percentages:

| Option | Shows |
| --- | --- |
| % of Grand Total | each cell's share of everything |
| % of Column Total | the share within a column |
| % of Row Total | the share within a row |
| Difference From | change against a previous item |
| Running Total In | cumulative totals |

For the pivot above, North's share of the grand total is 540 / 1100:



That is **49.1%**, which "% of Grand Total" would display for North.

## Grouping

| Field type | How to group |
| --- | --- |
| **Dates** | right-click a date, Group: Years, Quarters, Months (Excel 2016 and later can do this automatically) |
| **Numbers** | right-click, Group, then set a "By" size such as 10 to make marks bands 0-9, 10-19... |
| **Text** | select several items, right-click, Group, to make a custom category |

## Slicers, timelines and charts

| Feature | Purpose |
| --- | --- |
| **Slicer** (PivotTable Analyze, Insert Slicer) | clickable buttons to filter, shared by several pivots |
| **Timeline** | a date slider to filter by month or quarter |
| **PivotChart** | a chart linked to the pivot; it changes when you change the pivot |
| **Calculated Field** | a new field computed from others, such as `=Amount/Qty` for price |

## Refreshing

A PivotTable keeps a **snapshot** of the data. When the source changes, right-click the pivot and choose **Refresh** (or **Alt + F5**; refresh all with **Ctrl + Alt + F5**). Pivots built from a Table pick up added rows automatically on refresh. You can also set the pivot to refresh when the file opens.

## Common problems

| Problem | Cause |
| --- | --- |
| a field counts instead of sums | the column contains some text or blank cells, so Excel chose Count |
| new rows do not appear | the source was a plain range, not a Table, or you did not refresh |
| dates will not group | some dates are text or blank |
| "(blank)" shows up | empty cells in the source; fill or filter them out |
| formatting vanishes on refresh | turn on "Preserve cell formatting on update" in PivotTable Options |

:::tip
Use **GETPIVOTDATA** (what Excel inserts when you click a pivot cell from a formula) when you need a number out of a pivot for a report: it keeps working even if the pivot layout changes.
:::

:::interview
**Interviewers often ask:** "What is a PivotTable and why use it?" A tool that summarises large data by grouping and aggregating fields interactively, with no formulas, in seconds. Fields go to Rows, Columns, Values and Filters; it must be refreshed when the source data changes.
:::
