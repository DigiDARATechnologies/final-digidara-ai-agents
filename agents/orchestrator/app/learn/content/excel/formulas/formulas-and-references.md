---
title: Formulas and cell references
summary: Write formulas that calculate, and master relative, absolute and mixed references so one formula can be copied down and across.
takeaways:
- Every formula starts with =; Excel follows the order of operations
- A relative reference (B2) changes when copied; an absolute reference ($B$2) does not
- F4 cycles between the four reference styles
---
## Your first formulas

A formula begins with **=**. Use cell addresses instead of typing numbers, so the result updates when the data changes.

| Formula | Meaning |
| --- | --- |
| `=B2+B3` | add two cells |
| `=C2*0.18` | 18% of a cell |
| `=(B2-B3)/B3` | percentage change |
| `=B2^2` | B2 squared |
| `=A2&" "&B2` | join text together |

Excel calculates in the usual order: brackets, powers, multiply and divide, then add and subtract.



`=2+3*4` is **14** (multiplication first), and `=(2+3)*4` is **20**. Use brackets whenever you are unsure.

## Relative references

Type `=C2*0.18` in D2, then copy it down. Excel **adjusts the row** in each copy:

| Cell | Formula after copying down |
| --- | --- |
| D2 | `=C2*0.18` |
| D3 | `=C3*0.18` |
| D4 | `=C4*0.18` |

That is a **relative reference**: "the cell in the same column, this same row". It is what you want most of the time.

## Absolute references: the dollar sign

Now put a tax rate in a cell (F1 = 0.18) and write `=C2*F1`. Copied down, it becomes `=C3*F2`, which points to an empty cell. You want the tax cell to stay fixed. Add dollar signs:



| Reference | Behaviour when copied | Example |
| --- | --- | --- |
| `B2` (relative) | row and column both change | `=B2*2` |
| `$B$2` (absolute) | neither changes | `=C2*$F$1` |
| `B$2` (mixed) | row fixed, column changes | `=B$2*A3` |
| `$B2` (mixed) | column fixed, row changes | `=$B2*C$1` |

`$F$1` always points at F1, wherever the formula is copied. With the tax rate in **one** cell, changing it once updates every result.

Click inside a reference in the formula bar and press **F4** to cycle `B2` → `$B$2` → `B$2` → `$B2`.

## Mixed references: a multiplication table

One formula, copied across and down, fills a whole grid:

| | B | C | D |
| --- | --- | --- | --- |
| 1 | | 1 | 2 |
| 2 | 1 | | |
| 3 | 2 | | |

Put `=$B2*C$1` in C2 and copy it over the grid. `$B` keeps the column of the left-hand number fixed, and `$1` keeps the row of the top number fixed.



The four results are 1, 2, 2 and 4. Mixed references are the key to building tables from a single formula.

## Ranges and names

| You write | Meaning |
| --- | --- |
| `B2:B7` | a range of cells |
| `B2:D4` | a rectangular block |
| `B:B` | the whole column B |
| `Marks` | a **named range**: select cells, type a name in the Name box |
| `Sheet2!B2` | a cell on another sheet |
| `'My Sheet'!B2` | a sheet name with spaces needs quotes |

A named range makes formulas readable: `=SUM(Marks)` is easier to understand than `=SUM(C2:C7)`.

## Copying results as values

A formula depends on other cells. To keep only the **result** (for sending a file, or freezing a number), copy the cells and use **Paste Special, Values** (`Ctrl + Alt + V`, then `V`). The formulas are replaced by their current results.

:::warning
If you delete a cell that a formula uses, you get a `#REF!` error. If you cut and paste, Excel updates references; if you copy and paste, the new copy points relative to its new position. Learn the difference, because it explains many "my formula changed" surprises.
:::

:::interview
**Interviewers often ask:** "What is the difference between relative and absolute references?" A relative reference (B2) changes when the formula is copied; an absolute reference ($B$2) stays fixed. Mixed references (B$2, $B2) fix only the row or only the column. F4 toggles between them.
:::
