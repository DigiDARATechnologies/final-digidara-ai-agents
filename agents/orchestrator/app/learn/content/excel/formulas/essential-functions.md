---
title: Essential functions
summary: SUM, AVERAGE, COUNT, MIN, MAX, ROUND, RANK and friends: the functions you will use every single day.
takeaways:
- A function is a ready-made formula: =NAME(arguments)
- SUM, AVERAGE, COUNT, MIN, MAX and ROUND cover most daily work
- COUNT counts numbers, COUNTA counts non-empty cells, COUNTBLANK counts empty ones
---
## What is a function?

A **function** is a ready-made formula with a name: `=SUM(C2:C7)`. The values you give it inside the brackets are its **arguments**. Start typing a function and Excel shows a hint box for the arguments.

All results below use the student list from the first lesson (marks in C2:C7: 92, 48, 85, 71, 64, 55).

## Adding up and averaging

| Formula | Result | Meaning |
| --- | --- | --- |
| `=SUM(C2:C7)` | 415 | total |
| `=AVERAGE(C2:C7)` | 69.17 | mean |
| `=MEDIAN(C2:C7)` | 67.5 | middle value |
| `=MAX(C2:C7)` | 92 | highest |
| `=MIN(C2:C7)` | 48 | lowest |
| `=LARGE(C2:C7,2)` | 85 | second highest |
| `=SMALL(C2:C7,2)` | 55 | second lowest |



Press **Alt + =** under a column of numbers to insert `SUM` automatically.

## Counting

| Formula | Result | Counts |
| --- | --- | --- |
| `=COUNT(C2:C7)` | 6 | cells holding **numbers** |
| `=COUNTA(A2:A7)` | 6 | cells that are **not empty** (any kind) |
| `=COUNTBLANK(C2:C7)` | 0 | **empty** cells |



Here A1:A3 holds two names and an empty cell, and B1:B3 holds the number `10`, the word `ten` and the number `30`:

| Formula | Result | Why |
| --- | --- | --- |
| `=COUNT(B1:B3)` | 2 | only 10 and 30 are numbers |
| `=COUNTA(B1:B3)` | 3 | all three cells have something in them |
| `=COUNTA(A1:A3)` | 2 | the empty cell is not counted |

Use `COUNT` to count numbers and `COUNTA` to count entries of any kind.

## Rounding

| Formula | Result |
| --- | --- |
| `=ROUND(69.1667,1)` | 69.2 |
| `=ROUND(1234.5678,-2)` | 1200 |
| `=ROUNDUP(2.11,1)` | 2.2 |
| `=ROUNDDOWN(2.99,1)` | 2.9 |
| `=INT(7.9)` | 7 |
| `=MOD(17,5)` | 2 |



A negative number of digits rounds to the left of the decimal point (`-2` rounds to the nearest hundred).

## Ranking



`=RANK(B2,$B$2:$B$5)` gives Asha rank **1**, Ravi **4**, Meena **2** and Arun **3**. The range uses `$` so it stays fixed while the formula is copied down. Add `,1` as a third argument to rank from lowest to highest. In newer Excel, `RANK.EQ` is the same function.

## Useful extras

| Formula | Does |
| --- | --- |
| `=SUMPRODUCT(B2:B7,C2:C7)` | multiplies row by row, then adds: quantity times price, totalled |
| `=ABS(-5)` | removes the sign (5) |
| `=PRODUCT(2,3,4)` | multiplies (24) |
| `=SQRT(81)` | square root (9) |
| `=RAND()`, `=RANDBETWEEN(1,6)` | random numbers (they change on every recalculation) |



`SUMPRODUCT` of quantities 2, 3, 4 and prices 10, 20, 5 gives 2×10 + 3×20 + 4×5 = **100**: a whole bill in one formula.

:::tip
You can select a range and read **SUM, AVERAGE and COUNT in the status bar** at the bottom right, with no formula at all. Right-click the status bar to add more.
:::
