---
title: Dynamic array functions
summary: FILTER, SORT, UNIQUE, SEQUENCE, XLOOKUP and LET: formulas that return many values at once and spill into neighbouring cells.
takeaways:
- A dynamic array formula returns several values that spill into the cells below or beside it
- FILTER, SORT, SORTBY and UNIQUE replace many manual steps and pivots for lists
- LET names intermediate values, making long formulas shorter and faster
---
## Spilling

In Microsoft 365 and Excel 2021, a formula can return **many values**. Type it in **one** cell, press Enter, and the results **spill** into the cells below or to the right. A blue border shows the spill range. Refer to the whole spill with the **#** sign: `=SUM(F2#)`.



`=SORT(A1:A3)` typed in B1 fills B1:B3 with 1, 2, 3. If a spill range is blocked by other data, you get a `#SPILL!` error: clear the cells in the way.

Use the student list from the first lesson (Name A, Dept B, Marks C, City D, rows 2 to 7) in the examples below.

## FILTER

`=FILTER(array, include, [if_empty])` returns only the rows that match.

| Formula | Returns |
| --- | --- |
| `=FILTER(A2:C7,B2:B7="CSE")` | the CSE rows (Asha, Meena) |
| `=FILTER(A2:A7,C2:C7>=70)` | names with 70 or more: Asha, Meena, Arun |
| `=FILTER(A2:C7,(B2:B7="IT")+(C2:C7<60))` | IT **or** under 60 (the `+` means OR) |
| `=FILTER(A2:C7,(B2:B7="CSE")*(C2:C7>=90))` | CSE **and** 90+ (the `*` means AND) |
| `=FILTER(A2:A7,C2:C7>100,"nobody")` | shows "nobody" when nothing matches |



Three students scored 70 or more, there are three distinct departments, the highest mark is 92 and its owner is Asha, and the IT students' marks add up to 119.

## SORT and SORTBY

| Formula | Returns |
| --- | --- |
| `=SORT(A2:C7,3,-1)` | the whole table sorted by column 3 (marks), descending (-1) |
| `=SORTBY(A2:A7,C2:C7,-1)` | names ordered by marks, highest first |
| `=TAKE(SORT(A2:C7,3,-1),3)` | the top 3 rows (TAKE needs a recent Microsoft 365) |

Combine them: `=SORT(FILTER(A2:C7,B2:B7="CSE"),3,-1)` gives the CSE students, best first.

## UNIQUE

`=UNIQUE(B2:B7)` lists each department once (CSE, ECE, IT). Add `,FALSE,TRUE` to return only values that occur **exactly once**.

A **live summary table** with no pivot:

| Formula | Place in |
| --- | --- |
| `=UNIQUE(B2:B7)` | F2 (spills the departments) |
| `=SUMIFS(C2:C7,B2:B7,F2#)` | G2 (spills a total for each) |
| `=COUNTIFS(B2:B7,F2#)` | H2 (spills a count for each) |



The totals are CSE **177**, ECE **119** and IT **119**: the same as the earlier lessons, with no pivot to refresh. When data is added, the unique list and totals update automatically.

## SEQUENCE and other generators

| Formula | Returns |
| --- | --- |
| `=SEQUENCE(5)` | 1, 2, 3, 4, 5 down a column |
| `=SEQUENCE(3,4)` | a 3 by 4 grid of 1 to 12 |
| `=SEQUENCE(12,1,DATE(2026,1,1),30)` | a date every 30 days |
| `=RANDARRAY(3,2)` | a 3 by 2 grid of random decimals |
| `=TRANSPOSE(A1:A3)` | turns a column into a row |
| `=TEXTSPLIT(A1,",")` | splits text across cells |

## XLOOKUP that spills

A lookup can return a whole **row**: `=XLOOKUP("Meena",A2:A7,A2:D7)` returns Meena's name, department, marks and city across four cells.

## LET: give names to parts of a formula

`LET` assigns names to values or expressions, so you write long calculations once and read them easily. It also avoids calculating the same thing twice.



`=LET(marks,A1:A4,avg,AVERAGE(marks),COUNTIF(marks,">"&avg))` counts how many marks are above the average. With marks 92, 48, 85, 71 the average is 74, and **2** marks are above it.

## Other newer helpers

| Function | Does |
| --- | --- |
| `LAMBDA` | create your own named function from a formula |
| `MAP`, `REDUCE`, `SCAN`, `BYROW` | apply a calculation to every item or row |
| `VSTACK`, `HSTACK` | stack ranges on top of or beside each other |
| `TOCOL`, `TOROW`, `WRAPROWS` | reshape arrays |
| `TAKE`, `DROP`, `CHOOSECOLS` | pick parts of an array |

:::warning
Dynamic arrays need **Microsoft 365 or Excel 2021 and later**. Files with them opened in older Excel show `@` signs or `_xlfn` names and may not work. Check what your audience uses before sharing.
:::

:::interview
**Interviewers often ask:** "What are dynamic arrays?" Formulas that return multiple values and spill into neighbouring cells automatically (FILTER, SORT, UNIQUE, SEQUENCE, XLOOKUP, LET). They replace helper columns and many array-formula tricks, and `#` references the whole spill range.
:::
