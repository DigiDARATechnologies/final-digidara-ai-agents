---
title: Sort, filter and data validation
summary: Order and filter lists safely, use custom and multi-level sorts, and stop bad data at the door with validation and drop-downs.
takeaways:
- Sort the whole table, not a single column, or you scramble the rows
- Filters hide rows without deleting them; advanced filters and slicers go further
- Data validation prevents mistakes before they happen, and drop-down lists keep entries consistent
---
## Sorting

Click any cell in your data, then **Data, Sort A to Z** (or Z to A). Excel finds the whole block and sorts every row together.

:::warning
Never select **one column** and sort just that. If Excel offers "Expand the selection", say yes. If you sort only the marks column, the marks separate from the names and the data is silently ruined. Click **inside** the table, not on a column, and make sure there are no blank rows or columns in the block.
:::

For several levels, use **Data, Sort**:

| Level | Column | Order |
| --- | --- | --- |
| 1 | Dept | A to Z |
| 2 | Marks | Largest to smallest |

That puts CSE first, with its highest marks on top, then ECE, then IT.

You can also sort by **colour**, by **icon**, or by a **custom list** such as Low, Medium, High (instead of alphabetical).

## Filtering

Press **Ctrl + Shift + L** to turn filter buttons on or off. Click an arrow on a header:

| Filter type | Example |
| --- | --- |
| pick values | tick only CSE and IT |
| text filters | begins with, contains, does not contain |
| number filters | greater than 60, top 10, above average |
| date filters | this month, last quarter, between two dates |
| search box | type part of a word to narrow the list |
| filter by colour | show only highlighted cells |

Filtering **hides** rows; it never deletes them. A filtered column shows a small funnel icon. Clear filters with **Ctrl + Alt + L** or the Clear button.

Calculations on filtered data: `SUM` adds hidden rows too. Use `SUBTOTAL(109, C2:C7)` to add **only the visible** rows, or the `AGGREGATE` function:



With nothing filtered, both give 60. After you filter out the row holding 20, `SUM` still shows 60, but `SUBTOTAL(109, ...)` shows **40**, because it counts only what you can see.

## Slicers and the advanced filter

| Tool | Use |
| --- | --- |
| **Slicer** (on a Table or PivotTable: Insert, Slicer) | clickable buttons to filter, great for dashboards |
| **Advanced Filter** (Data, Advanced) | complex criteria and copy the result to another place |
| **Remove Duplicates** (Data tab) | keeps one copy of each repeated row |
| **FILTER function** | live, formula-based filtering (dynamic arrays lesson) |

## Data validation: stop mistakes early

Cleaning bad data later costs far more than preventing it. Select the cells, then **Data, Data Validation**.

| Rule | Setting | Stops |
| --- | --- | --- |
| whole number | between 0 and 100 | marks of 250 or negative marks |
| decimal | greater than 0 | a negative price |
| date | after 1-Jan-2026 | impossible dates |
| list | `CSE,ECE,IT` or a range | typos in department names |
| text length | at most 10 | an oversize ID |
| custom formula | `=COUNTIF($A:$A,A2)=1` | duplicate IDs |

In the dialog you can also set an **input message** (a hint when the cell is selected) and an **error alert** (Stop, Warning or Information) with your own text, for example "Marks must be a whole number from 0 to 100."

## Drop-down lists

Choose **Allow: List**. For the source, either type values separated by commas (`CSE,ECE,IT`) or point at a range. For a list that grows, point at a **Table column** or a dynamic range, so new items appear automatically:

```py
Source:  =Departments[Name]        # a Table column named Departments
Source:  =$H$2#                    # a spilled dynamic array in H2 (Microsoft 365)
```

Dependent drop-downs (pick a State, then only its Cities appear) use `INDIRECT` with named ranges, or `FILTER`.

:::warning
Validation only checks **typed** entries. **Pasted** values bypass it, and so does a value that was there before the rule. Use **Data, Data Validation, Circle Invalid Data** to find existing values that break your rule.
:::

## Protecting your work

| Goal | How |
| --- | --- |
| stop formulas being overwritten | unlock the input cells, then Review, Protect Sheet |
| lock structure (no new sheets) | Review, Protect Workbook |
| require a password to open | File, Info, Protect Workbook, Encrypt with Password |

:::tip
Combine validation with a **Table**: validation rules, formulas and formatting automatically extend to every new row you add.
:::
