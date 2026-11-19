---
title: What is Excel?
summary: Meet the workbook, worksheets, cells and ranges, learn the data types, and the keyboard shortcuts that save hours.
takeaways:
- A workbook holds worksheets; a worksheet is a grid of cells; a cell holds a value or a formula
- Every cell has an address such as B3, and a range such as B2:B7 is a block of cells
- Excel treats numbers, text, dates and logical values differently, so entering them correctly matters
---
## What Excel is for

Excel is a **spreadsheet**: a grid where you keep data and calculate on it. Almost every office uses it, for budgets, attendance, marks, sales reports, invoices and quick analysis. If you can work well in Excel, you can answer many business questions without writing a line of code.

| You can use it to | Example |
| --- | --- |
| store lists and tables | a student list, an inventory |
| calculate | totals, averages, pass or fail |
| clean and reshape data | fix names, remove duplicates |
| summarise | a pivot table of sales by region |
| visualise | a chart for a presentation |
| plan | loan EMI, budgets, "what if" cases |

## The layout

| Part | What it is |
| --- | --- |
| **Workbook** | the whole file (`.xlsx`) |
| **Worksheet** | one tab in the workbook (Sheet1, Sheet2...) |
| **Cell** | one box; it has an address made of its column letter and row number, like **B3** |
| **Range** | a block of cells, written `B2:B7` (from B2 down to B7) or `A1:D10` |
| **Formula bar** | shows what is **inside** the selected cell (the formula, not just its result) |
| **Name box** | shows the selected cell's address; type an address there to jump to it |
| **Ribbon** | the tabs of commands: Home, Insert, Formulas, Data, View |

A cell can show `85` while the formula bar shows `=B2+B3`. What you **see** is the result; what is **stored** is the formula.

## Data types

Excel decides what a cell holds by what you type:

| You type | Excel treats it as | Notes |
| --- | --- | --- |
| `85`, `12.5` | a **number** | right-aligned, can be calculated |
| `Asha` | **text** | left-aligned |
| `10/03/2026` | a **date** | stored as a number (days since 1900), shown as a date |
| `TRUE` | a **logical** value | the result of comparisons such as `=B2>50` |
| `=B2+B3` | a **formula** | starts with an equals sign |

Dates are really numbers. This is why you can subtract two dates to get days between them.



:::warning
A number typed with a stray space or an apostrophe (`' 85`) becomes **text**, and `SUM` ignores text. If a column of numbers is left-aligned and will not add up, it is probably stored as text. The cleaning lesson shows the fix.
:::

## Moving around fast

| Shortcut | Does |
| --- | --- |
| `Ctrl + Arrow` | jump to the edge of the data |
| `Ctrl + Shift + Arrow` | select to the edge of the data |
| `Ctrl + A` | select all (press twice inside a table) |
| `F2` | edit the cell you are on |
| `Ctrl + Z` / `Ctrl + Y` | undo / redo |
| `Ctrl + C`, `Ctrl + X`, `Ctrl + V` | copy, cut, paste |
| `Alt + =` | AutoSum the numbers above or beside |
| `Ctrl + ;` | enter today's date |
| `Ctrl + 1` | open Format Cells |
| `Alt + Enter` | a new line **inside** a cell |
| `F4` | cycle `$` signs on a reference (next lessons) |

:::tip
Learn the **Ctrl + Arrow** and **Ctrl + Shift + Arrow** pair first. On a list of 5,000 rows they replace a lot of scrolling and dragging.
:::

## How this course works

Every formula result in this course was calculated by a spreadsheet engine, not guessed. Examples use a small student list; type it in yourself and watch the formulas work.

| | A | B | C | D |
| --- | --- | --- | --- | --- |
| 1 | **Name** | **Dept** | **Marks** | **City** |
| 2 | Asha | CSE | 92 | Chennai |
| 3 | Ravi | ECE | 48 | Madurai |
| 4 | Meena | CSE | 85 | Chennai |
| 5 | Arun | ECE | 71 | Salem |
| 6 | Divya | IT | 64 | Madurai |
| 7 | Kiran | IT | 55 | Chennai |

:::note
This course is written for **Microsoft 365 / Excel 2021 on Windows**. A few newer functions (XLOOKUP, FILTER, UNIQUE, LET) need those versions or later, and menus on a Mac or an older version can look a little different. Google Sheets uses most of the same formulas.
:::
