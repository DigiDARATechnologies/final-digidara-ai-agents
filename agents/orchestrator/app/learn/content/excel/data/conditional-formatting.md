---
title: Conditional formatting
summary: Colour cells automatically by their values: highlight rules, data bars, colour scales, icon sets and custom formulas.
takeaways:
- Conditional formatting changes how cells look based on rules; the data is never changed
- Built-in rules cover highlights, top and bottom, data bars, colour scales and icons
- A formula rule can format a whole row based on one cell
---
## Why

A column of 200 numbers tells you little. A column where failures are red, toppers are green and the rest fade into the background tells you what matters at a glance. Conditional formatting applies the formatting **automatically**, and updates it when the data changes.

Select the cells, then **Home, Conditional Formatting**.

## Highlight cells rules

| Rule | Example |
| --- | --- |
| Greater than, Less than, Between, Equal to | marks below 50 in red |
| Text that contains | cities containing "Chen" |
| A date occurring | due dates this week |
| Duplicate values | repeated IDs |

## Top and bottom rules

Top 10 items, Top 10 %, Bottom 10 items, Above average, Below average. Use **Above Average** to highlight students ahead of the class average without computing it yourself.

## Data bars, colour scales and icon sets

| Visual | Best for |
| --- | --- |
| **Data bars** | comparing sizes inside the cell, like a tiny bar chart |
| **Colour scales** | a heat map (red to green) across a range |
| **Icon sets** | traffic lights, arrows or ticks for status |

Use them sparingly: a sheet with three kinds of formatting everywhere is harder to read than none.

## Formula rules: format the whole row

The most powerful option: **New Rule, Use a formula to determine which cells to format.** The formula is written **for the first cell** of your selection, and Excel adjusts it for every other cell.

To shade every student row where marks are below 50, select `A2:D7` and use the formula:

```py
=$C2<50
```

The dollar sign locks the **column** (always look at column C) while the row changes. Without the `$` the rule would shift sideways and format the wrong cells.

The formula behind each rule is just a normal logical test. To see what it returns for each row:



For these four students the test `=$C2<50` is TRUE for **Ravi and Kiran** (the rows that would turn red), and `=AND($B2="CSE",$C2>=85)` is TRUE for **Asha and Meena** (the CSE students with 85 or more).

## Useful formula rules

| Goal | Formula (first cell is row 2) |
| --- | --- |
| highlight a whole row for a status | `=$D2="Overdue"` |
| alternate row shading | `=MOD(ROW(),2)=0` |
| highlight dates in the past | `=$E2<TODAY()` |
| highlight duplicates in column A | `=COUNTIF($A:$A,$A2)>1` |
| highlight the maximum | `=$C2=MAX($C$2:$C$7)` |
| highlight blanks in a required column | `=$B2=""` |

## Managing rules

**Conditional Formatting, Manage Rules** shows every rule, lets you change the order, and has **Stop If True**. Choose **This Worksheet** at the top to see all of them. Copying cells copies their rules, and after lots of copy and paste a sheet can collect hundreds of overlapping rules, which slows it down, so tidy them occasionally.

| Task | How |
| --- | --- |
| copy the formatting only | Format Painter, or Paste Special, Formats |
| remove rules | Conditional Formatting, Clear Rules |
| a rule that follows added rows | apply it to a Table column |

:::warning
Do not rely on colour alone. About one in twelve men has some colour blindness, and printed copies may be black and white. Add text or an icon (a tick, "Overdue") along with the colour, and keep enough contrast.
:::

:::tip
Conditional formatting changes only the **look**. You cannot `SUM` "all the red cells". If you need to count or filter by a condition, put the condition in a **formula column** and use that to format and to filter.
:::
