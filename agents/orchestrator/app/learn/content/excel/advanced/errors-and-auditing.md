---
title: Errors and auditing formulas
summary: Read every Excel error value, trace and debug formulas, avoid circular references and write sheets others can trust.
takeaways:
- Each error (#DIV/0!, #N/A, #VALUE!, #REF!, #NAME?, #NUM!) points to a specific kind of problem
- Evaluate Formula, Trace Precedents and Show Formulas find what is wrong
- Handle expected errors deliberately; do not hide all of them
---
## The error values

| Error | Meaning | Typical cause |
| --- | --- | --- |
| `#DIV/0!` | divided by zero or an empty cell | `=A1/B1` where B1 is 0 |
| `#N/A` | value not available | a lookup that did not find its value |
| `#VALUE!` | the wrong type of value | text where a number is needed, mismatched range sizes |
| `#REF!` | a reference is invalid | a cell or sheet used by the formula was deleted |
| `#NAME?` | Excel does not recognise a name | a misspelt function or a missing named range |
| `#NUM!` | an impossible number | `=SQRT(-1)`, a very large result |
| `#NULL!` | a bad range intersection | a missing comma or colon between ranges |
| `#SPILL!` | a dynamic array cannot spill | something is blocking the cells it needs |
| `####` | not an error: the column is too narrow | widen the column |



`=IFERROR(1/0,"check")` shows **check**, and `IFNA` catches only `#N/A` (a lookup that found nothing), leaving other errors visible, which is usually the better, more precise choice for lookups. `ISNUMBER("5")` is **FALSE** because `"5"` in quotes is text.

## Fixing the common ones

| Error | What to check |
| --- | --- |
| `#DIV/0!` | guard it: `=IF(B1=0,0,A1/B1)` or `=IFERROR(A1/B1,0)` |
| `#N/A` | spelling, extra spaces, text versus number, an exact-match lookup range |
| `#VALUE!` | `ISNUMBER` on the inputs; text hiding in a number column |
| `#REF!` | undo the delete; avoid deleting cells that formulas use |
| `#NAME?` | spelling of the function; a newer function in an old Excel version |
| `#SPILL!` | clear the cells below or beside the formula |

## Tools to trace problems

| Tool (Formulas tab) | Does |
| --- | --- |
| **Evaluate Formula** | steps through a formula one part at a time, showing each intermediate result |
| **Trace Precedents** | arrows to the cells a formula **uses** |
| **Trace Dependents** | arrows to the cells that **use** this cell |
| **Show Formulas** (`Ctrl + ` `) | show every formula instead of its result |
| **Error Checking** | lists cells with common problems |
| **Watch Window** | keep an eye on key cells while you change others |
| **F9** in the formula bar | evaluate the highlighted part of a formula (press Esc to undo) |

When a long formula misbehaves, split it into helper cells, check each piece, then combine them again.

## Circular references

A formula that refers to its own cell, directly or through a chain, is a **circular reference**: `=A1+1` typed in A1. Excel warns you and shows 0.

Find the loop with **Formulas, Error Checking, Circular References**. The fix is almost always a logic mistake, such as a total that includes its own cell in the range (`=SUM(B2:B10)` placed in B10).

## Keeping a model trustworthy

| Practice | Why |
| --- | --- |
| one **inputs** area, everything else formulas | change one cell, results update |
| no numbers typed inside formulas (`*0.18`) | the 0.18 is hidden; put the rate in a labelled cell |
| consistent formulas down a column | a single hand-typed value among formulas is a classic hidden error |
| colour code: inputs blue, formulas black | anyone can see what may be changed |
| document assumptions on a notes sheet | the next person (or you in six months) will thank you |
| totals that cross-check | rows sum equals columns sum |
| protect formula cells | stops accidental overwriting |

A quick consistency test:



The row totals add to 100, the column totals add to the same 100, so the cross-check cell says **ok**. If someone overtypes a total with a number, this check would flag a mismatch.

:::tip
Excel is the most common place for hidden errors in business. Before sending a workbook: look for error values, check totals two ways, test with simple numbers whose answer you know, and have someone else look at it.
:::
