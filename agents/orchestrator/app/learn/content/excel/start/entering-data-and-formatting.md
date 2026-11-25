---
title: Entering data, formatting and tables
summary: Enter data quickly with AutoFill, format numbers, dates and currency correctly, and turn a range into an Excel Table.
takeaways:
- Formatting changes how a value looks, not what it is
- AutoFill and Flash Fill remove repetitive typing
- A Table (Ctrl+T) makes data easier to sort, filter, reference and extend
---
## Entering data

- Click a cell and type; **Enter** moves down, **Tab** moves right.
- Press **F2** to edit what is already in a cell.
- To type the same thing in many cells, select them, type, and press **Ctrl + Enter**.

## AutoFill: drag the small square

Select a cell (or two cells that show a pattern), then drag the **fill handle**, the small square at the bottom-right corner.

| You start with | Dragging gives |
| --- | --- |
| `1`, `2` | `3`, `4`, `5`... |
| `Mon` | `Tue`, `Wed`... |
| `Jan` | `Feb`, `Mar`... |
| `10`, `20` | `30`, `40`... |
| a formula | the formula, adjusted for each row |
| `Item 1` | `Item 2`, `Item 3`... |

Double-click the fill handle to fill **down as far as the neighbouring data goes**.

## Flash Fill: let Excel see the pattern

Type the first result by hand, then press **Ctrl + E**. If column A has `Asha Kumar` and you type `Asha` in B2, Flash Fill fills the first names for every row. It also works for initials, phone formats and combined text.

:::tip
Check Flash Fill results: it guesses a pattern, and a guess can be wrong for odd rows. For work that must be exact, use formulas (the text functions lesson).
:::

## Number formats: look, not value

Formatting changes how a cell **looks**; the underlying value stays the same. Press **Ctrl + 1** to open Format Cells.

| Format | 1234.5 shows as | Use for |
| --- | --- | --- |
| General | `1234.5` | the default |
| Number (2 decimals, separator) | `1,234.50` | quantities |
| Currency | `₹1,234.50` or `$1,234.50` | prices |
| Percentage | `0.875` shows `87.5%` | rates and shares |
| Date | `10-Mar-2026` | dates |
| Text | stays exactly as typed | phone numbers, ID codes with leading zeros |



Formatting never rounds the **stored** value: `=7/3` shown with 2 decimals looks like `2.33`, but later formulas still use `2.3333333...`. If you need the number itself rounded, use `ROUND` (the functions lesson).

:::warning
A phone number or an ID such as `007` typed into a General cell loses its leading zeros (it becomes the number `7`). Format the column as **Text** first, or type an apostrophe before the entry (`'007`).
:::

## Making it look professional

| Task | How |
| --- | --- |
| bold header row | select the row, `Ctrl + B` |
| fit column to its content | double-click the border between two column letters |
| wrap long text | Home, Wrap Text |
| merge cells for a title | Home, Merge & Center (avoid it inside data: it breaks sorting) |
| freeze the header row | View, Freeze Panes, Freeze Top Row |
| borders and fill colour | Home, Borders and Fill Colour |

Freeze the header row on any long list so the column names stay visible while you scroll.

## Convert a range into a Table

Click inside your data and press **Ctrl + T**. Tick "My table has headers".

| A Table gives you | Why it matters |
| --- | --- |
| filter buttons on every header | quick filtering and sorting |
| banded rows and a header style | looks tidy, with no manual formatting |
| it **grows** when you add a row | formulas and charts that use it update automatically |
| named references like `Students[Marks]` | formulas that read like English |
| a Total Row option | sums at a click |

Name it on the Table Design tab (for example `Students`). Then a formula such as `=SUM(Students[Marks])` keeps working as rows are added, which a fixed range like `C2:C7` would not.

:::remember
Keep your data in a clean block: **one header row, one record per row, one fact per column, no blank rows or columns, no merged cells.** Almost every Excel feature (sort, filter, pivot, lookup) works best with data shaped this way.
:::
