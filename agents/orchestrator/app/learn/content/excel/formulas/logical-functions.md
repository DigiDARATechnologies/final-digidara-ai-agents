---
title: Logical functions: IF, IFS, AND, OR
summary: Make a sheet decide: pass or fail, grades, bonus rules, with IF, IFS, AND, OR, NOT and IFERROR.
takeaways:
- IF(test, value if true, value if false) is the most useful function after SUM
- AND and OR combine several conditions; IFS replaces long nested IFs
- IFERROR hides errors you expect, but use it carefully
---
## Comparisons give TRUE or FALSE

| Operator | Meaning |
| --- | --- |
| `=` | equal to |
| `<>` | not equal to |
| `>`, `<` | greater than, less than |
| `>=`, `<=` | greater than or equal, less than or equal |

`=C2>=50` returns TRUE or FALSE. Wrap it in `IF` to return something meaningful.

## IF

`=IF(condition, value_if_true, value_if_false)`



With marks 92 in A1 and 48 in A2, the formula `=IF(A1>=50,"Pass","Fail")` gives **Pass** for 92 and **Fail** for 48. Text results go in quotes; numbers and cell references do not.

## AND, OR, NOT

| Formula | TRUE when |
| --- | --- |
| `=AND(C2>=50, D2>=75)` | **both** conditions are true |
| `=OR(B2="CSE", B2="IT")` | **at least one** is true |
| `=NOT(C2<50)` | the condition is false |



A student with a test mark of 80 and attendance of 90 passes `=IF(AND(A1>=50,B1>=75),"Eligible","Not eligible")`, and `=IF(OR(A1<40,B1<40),"Retake","OK")` gives OK because neither is below 40.

## Several outcomes: nested IF and IFS

Grades need more than two outcomes. You can nest `IF` inside `IF`, but it gets hard to read:

```py
=IF(C2>=90,"A",IF(C2>=75,"B",IF(C2>=50,"C","F")))
```

`IFS` (Excel 2019 and later) does the same job as a list of pairs, in order, and stops at the first TRUE:

```py
=IFS(C2>=90,"A", C2>=75,"B", C2>=50,"C", TRUE,"F")
```

The final `TRUE,"F"` is the "everything else" case.



For marks 92, 85, 71 and 48 both versions give **A, B, C, F**.

:::warning
Order matters in nested IF and IFS. Test from the **highest** boundary down (`>=90` before `>=75`); if you check `>=50` first, every passing mark gets a C.
:::

## Counting with conditions inside a formula



A helper column of 1s and 0s (1 when the mark is 50 or more), then `SUM`, counts the passes: 2 out of 3 here. The conditional-aggregates lesson shows a one-formula way (`COUNTIF`).

## IFERROR



`=IFERROR(A1/A2,"n/a")` shows **n/a** instead of `#DIV/0!` when A2 is 0, and shows the normal result otherwise.

:::warning
`IFERROR` hides **every** error, including real mistakes such as a misspelt lookup range. Use it where you expect a specific problem (division by zero, a missing lookup value), not to hide errors you have not looked at.
:::

## Reusable decision tables

If rules change often (grade boundaries, discount slabs), do not write them inside the formula. Put the boundaries in a small table and use a lookup (next lessons), so changing the rule means editing a cell, not a formula.

:::interview
**Interviewers often ask:** "How do you assign grades from marks?" With nested `IF` or, more readably, `IFS` checking from the highest boundary down. For rules that change, keep the boundaries in a table and use `LOOKUP` or `XLOOKUP` with an approximate match.
:::
