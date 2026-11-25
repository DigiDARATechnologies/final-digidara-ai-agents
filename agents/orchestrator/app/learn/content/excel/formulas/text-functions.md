---
title: Text functions
summary: Split, join, clean and reformat text with LEFT, MID, LEN, TRIM, SUBSTITUTE, TEXTJOIN, TEXT and more.
takeaways:
- LEFT, RIGHT and MID take parts of text; LEN measures it; FIND locates a character
- TRIM, CLEAN and SUBSTITUTE clean messy text
- & and TEXTJOIN join text; TEXT formats numbers and dates inside text
---
## Taking text apart

| Formula (A1 = `SkillDARA`) | Result |
| --- | --- |
| `=LEN(A1)` | 9 |
| `=LEFT(A1,5)` | Skill |
| `=RIGHT(A1,4)` | DARA |
| `=MID(A1,6,4)` | DARA (start at 6, take 4) |
| `=UPPER(A1)` | SKILLDARA |
| `=LOWER(A1)` | skilldara |
| `=PROPER("asha kumar")` | Asha Kumar |



## Finding and splitting

`FIND` returns the position of a character. Combine it with `LEFT` and `MID` to split text at a symbol, such as an email address:



For `asha.k@college.edu`, `FIND("@",A1)` is **7**, so `LEFT(A1,FIND("@",A1)-1)` returns the name **asha.k**, and `MID(...)` from just after the @ returns the domain **college.edu**.

| Function | Notes |
| --- | --- |
| `FIND("x", text)` | position of x, **case-sensitive**; error if missing |
| `SEARCH("x", text)` | like FIND but ignores case and allows `?` and `*` |
| `SUBSTITUTE(text, old, new)` | replace text anywhere inside |
| `REPLACE(text, start, count, new)` | replace by position |
| `TEXTBEFORE`, `TEXTAFTER`, `TEXTSPLIT` | newer shortcuts for splitting (Microsoft 365) |

In Microsoft 365, **Text to Columns** (Data tab) and **Flash Fill** (Ctrl + E) are even faster for one-off splitting.

## Cleaning



`SUBSTITUTE` removes or replaces text: `abc`, `a b c`, and (with the last argument 1) only the **first** match is changed, giving `Hi Hello`.

| Formula | Does |
| --- | --- |
| `=TRIM(A1)` | removes leading and trailing spaces and squeezes repeated inner spaces to one |
| `=CLEAN(A1)` | removes non-printing characters (common in text pasted from the web) |
| `=SUBSTITUTE(A1,CHAR(160)," ")` | turns non-breaking spaces (from web pages) into normal spaces |
| `=VALUE("85")` | turns text that looks like a number into a real number |
| `=A1*1` or `=--A1` | a quick way to convert text numbers |

Combine them for names pasted with odd spacing: `=PROPER(TRIM(A1))` turns `"  asha   KUMAR "` into `Asha Kumar`.

## Joining text



| Formula | Result |
| --- | --- |
| `=A1&" ("&B1&")"` | Asha (CSE) |
| `=CONCAT(A1,"-",B1)` | Asha-CSE |
| `=TEXTJOIN(", ",TRUE,A1:A3)` | Asha, Ravi, Meena |
| `=TEXTJOIN(" \| ",TRUE,A1,C1,B1)` (C1 is empty) | Asha \| CSE |

`TEXTJOIN(separator, ignore_empty, items...)` is the best choice for lists: the second argument `TRUE` skips empty cells (such as C1 above) so you do not get stray separators. The older `CONCATENATE` still works but `&`, `CONCAT` and `TEXTJOIN` are better.

## TEXT: format a number or date inside text



Joining a number straight into text shows the raw number (`"Total: "&1234.5` gives `Total: 1234.5`). `TEXT` controls how it looks: `1,234.50`, `88%`, `10-Mar-2026`, or padding with zeros (`007`).

## Practical patterns

| Goal | Formula |
| --- | --- |
| initials from a full name in A1 | `=LEFT(A1,1)&MID(A1,FIND(" ",A1)+1,1)` |
| generate an ID | `="STU"&TEXT(ROW()-1,"000")` gives STU001, STU002... |
| check a value contains text | `=ISNUMBER(SEARCH("data",A1))` |
| count words | `=LEN(TRIM(A1))-LEN(SUBSTITUTE(TRIM(A1)," ",""))+1` |



These give **AK**, **TRUE** and **3** for the sample text.

:::tip
Text functions return **text**, even when the result looks like a number: `=LEFT("2026-03",4)` gives the text `2026`. Wrap it in `VALUE()` (or multiply by 1) before using it in calculations.
:::
