---
title: Conditional totals: SUMIF, COUNTIF and friends
summary: Add, count and average only the rows that meet your conditions, with SUMIFS, COUNTIFS, AVERAGEIFS, MAXIFS and wildcards.
takeaways:
- SUMIF, COUNTIF and AVERAGEIF work with one condition; the S versions allow many
- Conditions can be text, numbers, comparisons (">=50") or wildcards ("A*")
- Combine criteria with & to build conditions from cells
---
## One condition: SUMIF, COUNTIF, AVERAGEIF

Use the student list: Dept in B2:B7, Marks in C2:C7, City in D2:D7.

| Formula | Result | Meaning |
| --- | --- | --- |
| `=COUNTIF(B2:B7,"CSE")` | 2 | students in CSE |
| `=SUMIF(B2:B7,"CSE",C2:C7)` | 177 | total CSE marks |
| `=AVERAGEIF(B2:B7,"CSE",C2:C7)` | 88.5 | average CSE marks |
| `=COUNTIF(C2:C7,">=50")` | 5 | students with 50 or more |
| `=COUNTIF(C2:C7,"<>48")` | 5 | not equal to 48 |



The pattern is `SUMIF(where to look, what to match, what to add)`. The range to add is the **last** argument; for `COUNTIF` there is nothing to add, so it has only two.

Conditions with an operator are written as **text** in quotes: `">=50"`, `"<>48"`, `"<100"`.

## Several conditions: SUMIFS, COUNTIFS, AVERAGEIFS

The S versions take the **range to add first**, then pairs of (range, condition):

`=SUMIFS(sum_range, criteria_range1, criteria1, criteria_range2, criteria2, ...)`



| Formula | Result | Meaning |
| --- | --- | --- |
| `=COUNTIFS(B2:B7,"ECE",C2:C7,">=50")` | 1 | ECE students who passed (Arun) |
| `=SUMIFS(C2:C7,D2:D7,"Chennai",C2:C7,">=60")` | 177 | marks of Chennai students with 60+ (92 + 85) |
| `=AVERAGEIFS(C2:C7,B2:B7,"IT")` | 59.5 | average IT marks |
| `=MAXIFS(C2:C7,B2:B7,"ECE")` | 71 | the highest ECE mark |
| `=MINIFS(C2:C7,D2:D7,"Chennai")` | 55 | the lowest Chennai mark |

All conditions must be true together (**AND**). For **OR**, add two COUNTIFs: `=COUNTIF(B2:B7,"CSE")+COUNTIF(B2:B7,"IT")`.

:::warning
All the ranges in a SUMIFS must be the **same size**. A range of 6 cells next to one of 7 gives `#VALUE!`.
:::

## Conditions from cells

Do not type the department into the formula. Point at a cell, and the formula works for every row you copy it to:



The totals per department come out as CSE **177**, ECE **119**, IT **119**. To use a comparison with a cell, join them with `&`: `">"&I1` becomes `">70"` when I1 holds 70, which counts **3** students above 70 (92, 85 and 71).

## Wildcards

| Pattern | Matches |
| --- | --- |
| `"A*"` | text starting with A |
| `"*a"` | text ending in a |
| `"*ee*"` | text containing "ee" |
| `"???"` | exactly three characters |
| `"~*"` | a literal asterisk |



In Asha, Arun, Ravi, Meena: names starting with A = **2**, ending in "a" = **2** (Asha, Meena), and exactly four letters = **3** (Asha, Arun, Ravi).

## SUMPRODUCT: when you need OR logic or maths



`SUMPRODUCT` multiplies arrays of TRUE/FALSE tests, so it can count **CSE students with 90 or more** (1) or add the marks of **CSE or IT** students (296) in one formula. It is slower on large data, so use the IFS functions when they are enough.

:::interview
**Interviewers often ask:** "What is the difference between SUMIF and SUMIFS?" SUMIF has one condition and the range to add comes last. SUMIFS allows many conditions (all must be true) and takes the range to add **first**. The same pattern applies to COUNTIF(S) and AVERAGEIF(S).
:::
