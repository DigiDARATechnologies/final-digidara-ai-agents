---
title: Lookup functions
summary: Find values in tables with VLOOKUP, XLOOKUP and INDEX MATCH, use exact and approximate matching, and avoid the classic mistakes.
takeaways:
- Lookups find a value in one column and return a value from another
- XLOOKUP is the modern choice; INDEX MATCH works everywhere; VLOOKUP is everywhere but fragile
- Use exact match unless you are looking up ranges such as grade bands
---
## The idea

You have a student list and a separate table of marks. For each student you want to **look up** their marks by name. A lookup takes a value, finds it in one column and returns something from the same row.

All examples use this table in A2:C6:

| | A | B | C |
| --- | --- | --- | --- |
| 1 | **ID** | **Name** | **Marks** |
| 2 | 101 | Asha | 92 |
| 3 | 102 | Ravi | 48 |
| 4 | 103 | Meena | 85 |
| 5 | 104 | Arun | 71 |
| 6 | 105 | Divya | 64 |

## VLOOKUP

`=VLOOKUP(lookup_value, table, column_number, FALSE)`



- `=VLOOKUP(103,A2:C6,3,FALSE)` finds 103 in the first column and returns the 3rd column: **85**.
- `=VLOOKUP(104,A2:C6,2,FALSE)` returns **Arun**.
- For an ID that does not exist, `IFERROR` turns the `#N/A` into "not found".

The last argument matters: **FALSE** means exact match (what you almost always want). Leaving it out or using TRUE does an approximate match that can quietly return a wrong row.

:::warning
VLOOKUP weaknesses: it only looks to the **right** of the lookup column, the column number breaks if someone inserts a column in the table, and an accidental approximate match gives wrong answers without an error. These are reasons to prefer XLOOKUP or INDEX MATCH.
:::

## XLOOKUP (Microsoft 365 and Excel 2021)

`=XLOOKUP(lookup_value, lookup_range, return_range, if_not_found)`



| Formula | Result |
| --- | --- |
| `=XLOOKUP("Ravi",B2:B6,C2:C6)` | 48 |
| `=XLOOKUP(105,A2:A6,B2:B6)` | Divya |
| `=XLOOKUP("Zoya",B2:B6,C2:C6,"not found")` | not found |
| `=XLOOKUP(85,C2:C6,B2:B6)` | Meena (it can look **left**: marks to name) |

Why it is better: you point at the **lookup column** and the **result column** directly, so inserting columns cannot break it; exact match is the default; it looks in any direction; and it has a built-in "if not found" message. It can also return several columns at once (`C2:D6`) and search from the bottom (the sixth argument).

## INDEX and MATCH

The combination that worked before XLOOKUP, and works in **every** version:

- `MATCH(value, range, 0)` returns the **position** of the value in the range.
- `INDEX(range, position)` returns the item at that position.



`MATCH("Meena",B2:B6,0)` is **3** (the third item), `INDEX(C2:C6,3)` is **85**, and nested together, `=INDEX(C2:C6,MATCH("Meena",B2:B6,0))` finds Meena's marks (**85**). The `0` means exact match. It can look in any direction, like XLOOKUP.

## Approximate match: grade bands

Sometimes you do not want an exact value but the **band** a number falls into. Make a table of the **lower limits**, sorted ascending:

| | E | F |
| --- | --- | --- |
| 1 | **From** | **Grade** |
| 2 | 0 | F |
| 3 | 50 | C |
| 4 | 75 | B |
| 5 | 90 | A |



- `=XLOOKUP(92,E2:E5,F2:F5,,-1)` returns **A**: the match mode `-1` means "exact, or the next smaller value".
- 71 falls between 50 and 75, so the same formula gives **C**; 48 gives **F**.
- `=VLOOKUP(92,E2:F5,2,TRUE)` also gives **A** (TRUE means approximate, and the table must be sorted ascending); 75 gives **B**.

Changing a grade boundary now means editing a cell in the table, not editing formulas.

## Looking up across sheets and many criteria

| Need | Approach |
| --- | --- |
| a table on another sheet | `=XLOOKUP(A2,Prices!A:A,Prices!B:B)` |
| match **two** columns (name and class) | add a helper column `=A2&"\|"&B2` and look that up, or use `FILTER` (dynamic arrays lesson) |
| return a whole row | `=XLOOKUP(101,A2:A6,A2:C6)` spills across |
| first match only | lookups return the **first** match; duplicates are ignored |

:::tip
Before looking up, make sure the lookup column is clean: no extra spaces and the same data type on both sides (the **number** 101 and the **text** "101" do not match). `TRIM` and `VALUE` fix most mismatches.
:::

:::interview
**Interviewers often ask:** "VLOOKUP versus XLOOKUP versus INDEX MATCH?" VLOOKUP only looks right and breaks if columns are inserted. INDEX MATCH looks in any direction and works in every version. XLOOKUP is the modern replacement: simpler syntax, exact match by default, looks any direction and has a built-in not-found value.
:::
