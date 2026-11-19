---
title: Excel interview questions
summary: Excel questions for freshers and analysts, from basic formulas to lookups, pivot tables and data cleaning, with answers you can say aloud.
kind: qa
takeaways:
- Know relative versus absolute references, IF, SUMIFS and the lookup functions cold
- Be ready to explain pivot tables, data validation and how you clean data
- Show you think about accuracy: error handling, checks and documentation
---
### Q [Easy] What is the difference between a workbook and a worksheet?
A workbook is the whole Excel file. A worksheet is a single tab (grid of rows and columns) inside it. One workbook can hold many worksheets.

### Q [Easy] What is a cell reference, and what are relative and absolute references?
A cell reference is a cell's address, such as B3. A relative reference (B3) changes when the formula is copied. An absolute reference ($B$3) always points to the same cell. A mixed reference fixes only the row (B$3) or only the column ($B3). F4 toggles them.

### Q [Easy] How do you add numbers, and what is AutoSum?
With the SUM function, for example `=SUM(C2:C7)`. AutoSum (Alt + =) inserts it automatically for the numbers above or beside the selected cell.

### Q [Easy] What is the difference between COUNT, COUNTA and COUNTBLANK?
COUNT counts cells containing numbers. COUNTA counts cells that are not empty (numbers, text, anything). COUNTBLANK counts empty cells.

### Q [Medium] Explain the IF function and give an example.
`=IF(condition, value_if_true, value_if_false)`. For example `=IF(C2>=50,"Pass","Fail")`. It can be nested for several outcomes, or use IFS for a cleaner list of conditions, and combined with AND and OR for multiple tests.

### Q [Medium] How do SUMIF and SUMIFS differ?
SUMIF has one condition and takes the sum range last: `SUMIF(range, criteria, sum_range)`. SUMIFS accepts many conditions (all must be true) and takes the sum range first: `SUMIFS(sum_range, range1, criteria1, range2, criteria2)`.

### Q [Medium] What is the difference between VLOOKUP and XLOOKUP?
VLOOKUP searches only the first column of a table and returns a value from a column number to the right; it breaks if columns are inserted and uses approximate match unless FALSE is given. XLOOKUP takes separate lookup and return ranges, looks in any direction, defaults to exact match, and has a built-in "not found" argument.

### Q [Medium] How does INDEX MATCH work and why use it?
MATCH returns the position of a value in a range, and INDEX returns the item at that position: `=INDEX(C2:C6, MATCH("Meena", B2:B6, 0))`. It can look left, does not break when columns are inserted, and works in all Excel versions.

### Q [Medium] What does the 4th argument of VLOOKUP do?
`range_lookup`. FALSE (or 0) means exact match. TRUE (or omitted) means approximate match, which needs the first column sorted ascending and returns the nearest lower value, useful for grade bands but dangerous if used by mistake.

### Q [Medium] What is a PivotTable and when do you use it?
A tool that summarises large data by grouping and aggregating fields (Rows, Columns, Values, Filters) without formulas, so you can answer questions like total sales by region and product quickly. It needs tidy source data and must be refreshed when the data changes.

### Q [Medium] How do you handle duplicates?
To find them: conditional formatting for duplicate values or `COUNTIF`. To remove them: Data, Remove Duplicates (after choosing the key columns and keeping a backup), or the `UNIQUE` function to get a list without changing the source.

### Q [Medium] How do you clean messy data in Excel?
Keep the original, then use TRIM, CLEAN, PROPER and VALUE for text and numbers stored as text, Text to Columns or Flash Fill for splitting, Find and Replace for consistent names, Remove Duplicates, and data validation to prevent bad entries. For repeated jobs use Power Query.

### Q [Medium] What is data validation?
A rule that restricts what can be entered in a cell, such as a whole number from 0 to 100, a date range, or a drop-down list. It prevents errors at entry, though pasted values can bypass it.

### Q [Medium] What are the common Excel errors and what do they mean?
`#DIV/0!` divide by zero; `#N/A` a lookup value not found; `#VALUE!` wrong data type; `#REF!` an invalid or deleted reference; `#NAME?` an unrecognised function or name; `#NUM!` an invalid number; `#SPILL!` a dynamic array blocked.

### Q [Medium] What is the difference between a formula and a function?
A formula is any calculation starting with `=`, such as `=A1+B1*2`. A function is a built-in named routine such as SUM or IF that you use inside formulas.

### Q [Medium] How do you freeze panes and why?
View, Freeze Panes. It keeps the header row or first columns visible while scrolling through long data, so you always know which column you are looking at.

### Q [Hard] How would you find the second highest mark, or the top three, without sorting?
`=LARGE(C2:C7,2)` for the second highest, and `LARGE` with 1, 2, 3 for the top three. In Microsoft 365, `=TAKE(SORT(C2:C7,,-1),3)` returns the top three at once. For matching names use `XLOOKUP` or `INDEX MATCH` on the result.

### Q [Hard] How do you do a lookup with two conditions?
Create a helper column that joins the two columns (`=A2&"|"&B2`) and look that up, or use `FILTER` with `(range1=a)*(range2=b)`, or `SUMIFS` when the result is a number. `INDEX MATCH` with an array `MATCH(1,(A:A=a)*(B:B=b),0)` also works.

### Q [Hard] What are dynamic arrays, and name some functions?
Formulas that return several values and spill into neighbouring cells automatically: FILTER, SORT, SORTBY, UNIQUE, SEQUENCE, XLOOKUP and LET. They reduce helper columns, and `#` refers to a whole spill range. They need Microsoft 365 or Excel 2021 and later.

### Q [Hard] What is Power Query and why is it useful?
A data-preparation tool built into Excel that records transformation steps (remove columns, change types, split, merge, unpivot) and replays them on refreshed data, with a load into a table or the Data Model. It makes recurring clean-up repeatable and removes manual work and errors.

### Q [Hard] How do you make a spreadsheet reliable for others?
Separate inputs, calculations and outputs; keep numbers out of formulas; use consistent formulas and Tables; add data validation and cross-check totals; handle expected errors deliberately; protect formula cells; and document assumptions. Test with simple numbers whose answers you know.

:::practice mock-interview
Practise explaining VLOOKUP versus XLOOKUP, absolute references and PivotTables aloud in a Mock Interview.
:::
