---
title: Cleaning messy data
summary: Fix numbers stored as text, extra spaces, duplicates, inconsistent names and split columns with Text to Columns, Flash Fill and formulas.
takeaways:
- Messy data is the normal case; cleaning comes before every analysis
- Text to Columns, Remove Duplicates, Find and Replace and Flash Fill fix most problems quickly
- Use formulas in helper columns when you need a repeatable, auditable clean-up
---
## Typical problems

| Symptom | Cause | Fix |
| --- | --- | --- |
| numbers left-aligned, totals wrong | numbers stored as **text** | Text to Columns, `VALUE`, or Paste Special multiply |
| `Asha` and `asha ` counted separately | extra spaces, different case | `TRIM`, `PROPER` |
| `Chennai`, `chennai`, `Chenai` | inconsistent spelling | Find and Replace, a lookup table, data validation |
| one column holds "Asha Kumar" | needs splitting | Text to Columns or Flash Fill |
| repeated rows | copy-paste errors | Remove Duplicates |
| dates that do not sort | dates stored as text | `DATEVALUE`, Text to Columns with a Date format |
| strange characters, extra spaces | pasted from a web page | `CLEAN`, `SUBSTITUTE(A1,CHAR(160)," ")` |

## Numbers stored as text



When `85` and `70` are stored as **text** and `60` is a real number, `SUM(A1:A3)` returns just **60**: it silently ignores the text. Converting with `VALUE`, `*1` or `--` gives the correct **215**.

Fast fix without formulas: type `1` in a blank cell, copy it, select the text numbers, **Paste Special, Multiply**. Or select the column and use **Data, Text to Columns, Finish**, which re-reads each cell as a number. A small green triangle in the corner of a cell also offers "Convert to Number".

## Spaces and case



`=LEN(A1)` is **15** for `"  asha   KUMAR "` although the name has only 9 letters: the other 6 characters are spaces. In real Excel, `=PROPER(TRIM(A1))` produces `Asha Kumar`: TRIM removes leading and trailing spaces and reduces runs of spaces between words to a single space.

A clean-up chain you will reuse: `=PROPER(TRIM(CLEAN(A1)))`.

## Splitting one column into two

**Text to Columns** (Data tab): select the column, choose **Delimited**, tick the separator (space, comma, hyphen), and pick a destination so you do not overwrite neighbouring data. **Fixed width** splits by character positions.

With formulas (so it updates when the data changes):



`Asha Kumar` splits into **Asha** and **Kumar**. In Microsoft 365, `=TEXTSPLIT(A1," ")` does it in one step.

## Remove Duplicates and find them first

**Data, Remove Duplicates** deletes repeated rows after you choose which columns define a duplicate. It cannot be undone after saving, so copy the data to a new sheet first.

To **see** duplicates before deleting: select the column, **Home, Conditional Formatting, Highlight Cells Rules, Duplicate Values**. To count them with a formula:



A count of 2 or more flags a duplicate. The expanding range `$A$1:A1` (fixed start, moving end) marks only the **second and later** copies as duplicates, keeping the first.

## Find and Replace

**Ctrl + H** opens it. Useful options: **Match entire cell contents** (so replacing `IT` does not change `City`), **Look in: Formulas or Values**, and wildcards (`*` and `?`). To find stray spaces use a space; to remove line breaks, press **Ctrl + J** in the Find box and replace with a space.

## Flash Fill

Type the first example result beside your data, then **Ctrl + E**. Great for extracting initials, reformatting phone numbers (`98765 43210`), or combining columns. Always scan the result: it only guesses the pattern.

## A safe cleaning routine

1. **Keep the original.** Copy the raw data to its own sheet and never edit it.
2. Convert the data to a Table (`Ctrl + T`).
3. Use **helper columns** with formulas (`TRIM`, `VALUE`, `PROPER`) so every step is visible.
4. Check for duplicates and blanks.
5. Paste Special, **Values** to freeze the clean result, then delete the helper columns.
6. Add **data validation** so the mess does not come back.

:::tip
For large or repeating clean-ups (monthly files with the same problems), use **Power Query** (the Power Query lesson). It records your steps once and replays them on new data with one click.
:::
