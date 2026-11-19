---
title: Power Query, macros and working with other tools
summary: Import and clean data with Power Query, record macros, meet Office Scripts and Python in Excel, and share workbooks safely.
takeaways:
- Power Query records your clean-up steps and replays them on fresh data
- Macros (VBA) automate repeated clicks; Office Scripts and Power Automate do it in the cloud
- Keep source data, calculations and reports separate, and protect what must not change
---
## Power Query: repeatable data preparation

If you clean the same monthly file the same way every time (delete columns, fix dates, trim spaces, combine files), you are repeating work. **Power Query** records each step once and replays all of them with a click.

**Data, Get Data** can import from:

| Source | Examples |
| --- | --- |
| files | Excel, CSV, text, PDF, a whole **folder** of files |
| databases | SQL Server, MySQL, PostgreSQL |
| the web | a table on a web page, an API |
| online services | SharePoint, Google Analytics and many more |

The **Power Query Editor** opens with your data and a list of **Applied Steps** on the right. Each action you take adds a step, and you can click an earlier step to see the data at that point.

| Common transformation | Menu |
| --- | --- |
| remove, rename, reorder columns | Home, Choose Columns; or right-click a header |
| change a data type (text, number, date) | click the icon in the column header |
| trim, clean, change case | Transform, Format |
| split a column | Transform, Split Column |
| fill blanks downwards | Transform, Fill, Down |
| remove duplicates, blanks, errors | Home, Remove Rows |
| unpivot columns into rows | Transform, Unpivot Columns |
| add a calculated column | Add Column, Custom Column |
| combine two tables | Home, Merge Queries (a join, like VLOOKUP but for whole tables) |
| stack tables | Home, Append Queries |

**Close & Load** puts the result into a worksheet or the Data Model. When next month's file arrives, replace the source and click **Data, Refresh All**: every step runs again.

### Unpivot: the most useful trick

Data often arrives with months across the top (Jan, Feb, Mar columns). Pivot tables and charts want one row per fact. **Unpivot** turns:

| Name | Jan | Feb |
| --- | --- | --- |
| Asha | 80 | 90 |

into

| Name | Month | Marks |
| --- | --- | --- |
| Asha | Jan | 80 |
| Asha | Feb | 90 |

## The Data Model and Power Pivot

When data is in several related tables (Orders, Customers, Products), **Power Pivot** lets you relate them, like a small database, and build a PivotTable across all of them without VLOOKUP. Its formula language is **DAX** (for example `Total Sales := SUM(Orders[Amount])`). It handles millions of rows that a normal sheet cannot.

## Macros and VBA

A **macro** records your clicks as code and plays them back. Use it for repetitive formatting or reports.

1. **View, Macros, Record Macro.** Give it a name.
2. Do the steps once.
3. **Stop Recording.** Run it from **Macros** or a button.

Save such a workbook as **.xlsm** (macro-enabled). Edit the code with **Alt + F11** (the VBA editor):

```py
Sub FormatHeader()
    With Range("A1:D1")
        .Font.Bold = True
        .Interior.Color = RGB(10, 167, 201)
        .Font.Color = vbWhite
    End With
    Columns("A:D").AutoFit
End Sub
```

:::warning
Macros can contain malicious code, which is why Excel disables them in files from the internet. Never enable macros in a file you do not trust, and do not send macro files as email attachments expecting them to work.
:::

## Modern automation

| Tool | Use |
| --- | --- |
| **Office Scripts** (Excel on the web) | TypeScript-based automation, runs in the cloud |
| **Power Automate** | connect Excel to email, Teams, forms: "when a form is submitted, add a row" |
| **Python in Excel** (Microsoft 365) | run pandas code inside a cell for analysis and charts |
| **Excel and Python outside Excel** | read and write workbooks with `pandas` and `openpyxl` |

If you know Python, `pandas.read_excel("sales.xlsx")` loads a sheet straight into a DataFrame, and `df.to_excel("report.xlsx")` writes the result back: ideal when files have millions of rows or the same job runs every week.

## Working with others

| Need | Feature |
| --- | --- |
| edit together | save to OneDrive or SharePoint, then **Share**: real-time co-authoring |
| leave feedback | **Comments** and **Notes** |
| track changes | **Version History** (File, Info) on cloud files |
| send a safe copy | **Paste Special, Values** the results or save as **PDF** |
| stop accidental edits | Protect Sheet; Mark as Final; "Open read-only" |
| remove private data | File, Info, Check for Issues, **Inspect Document** (hidden sheets, personal info) |

## Structure a workbook well

A workbook that other people can use and trust usually has these sheets:

| Sheet | Contains |
| --- | --- |
| **README / Notes** | what the file is for, version, who owns it, assumptions |
| **Data** (raw) | the untouched source, as a Table |
| **Inputs** | rates, dates and settings the user may change |
| **Calc** | formulas and helper columns |
| **Report / Dashboard** | the charts and numbers readers see |

:::tip
Learn to leave Excel when it stops being the right tool: millions of rows, many users editing at once, or a process that must run unattended belong in a database and a script. Excel is wonderful for **thinking with data**, and not always the best place to **keep** it.
:::
