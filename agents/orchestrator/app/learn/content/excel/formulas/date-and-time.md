---
title: Dates and time
summary: Calculate with dates: differences, ages, due dates, month ends, working days, and pull out parts with YEAR, MONTH and WEEKDAY.
takeaways:
- Dates are numbers, so subtraction gives days between them
- DATEDIF gives whole years, months or days; EDATE and EOMONTH move by months
- NETWORKDAYS counts working days and can skip holidays
---
## Dates are numbers

Excel stores a date as the number of days since 1 January 1900, so you can add and subtract them. Format the cell as a date to see it as a date.

| Function | Meaning |
| --- | --- |
| `=TODAY()` | today's date (updates every day) |
| `=NOW()` | the date and time right now |
| `=DATE(2026,3,10)` | build a date from year, month, day |
| `=YEAR(A1)`, `=MONTH(A1)`, `=DAY(A1)` | take a date apart |
| `=WEEKDAY(A1,2)` | day of the week (Monday = 1 when the second argument is 2) |



10 March 2026 is a **Tuesday**, which `WEEKDAY(A1,2)` reports as **2**.

## Differences



| Formula | Result | Meaning |
| --- | --- | --- |
| `=A2-A1` or `=DAYS(A2,A1)` | 9 | days between 1 and 10 March |
| `=DATEDIF(start, end, "Y")` | 6 | completed years from 15 Jan 2020 to 10 Mar 2026 |
| `=DATEDIF(start, end, "M")` | 73 | completed months (the 74th would finish on 15 March) |
| `=DATEDIF(start, end, "D")` | days | |
| `=DATEDIF(start, end, "YM")` | months left after the years | |

To show an age such as "6 years, 1 month": `=DATEDIF(B2,TODAY(),"Y")&" years, "&DATEDIF(B2,TODAY(),"YM")&" months"`. `DATEDIF` works but does not appear in the function hints, so you must type it fully.

## Moving by months



| Formula (A1 = 31 Jan 2026) | Result | Meaning |
| --- | --- | --- |
| `=EDATE(A1,1)` | 28-Feb-2026 | the same day next month (clipped to the month's end) |
| `=EOMONTH(A1,0)` | 31-Jan-2026 | the last day of A1's month |
| `=EOMONTH(A1,1)` | 28-Feb-2026 | the last day of next month |
| `=EOMONTH(A1,-1)+1` | 01-Jan-2026 | the **first** day of A1's month |

`EOMONTH` is the standard way to get month ends and month starts (it handles different month lengths and leap years for you).

## Working days



| Formula | Result | Meaning |
| --- | --- | --- |
| `=NETWORKDAYS(A1,A2)` | 10 | working days (Monday to Friday) from 2 to 13 March 2026, both included |
| `=NETWORKDAYS(A1,A2,A3)` | 9 | the same, but treating the date in A3 (6 March) as a holiday |
| `=WORKDAY(A1,5)` | 09-Mar-2026 | the date **5 working days after** 2 March |

For countries with different weekends use `NETWORKDAYS.INTL` and `WORKDAY.INTL`.

## Time

Times are fractions of a day: 12:00 is 0.5, and 6:00 is 0.25.



A shift from 9:30 to 17:45 is **8.25 hours**, shown as `8:15`. Multiply a time difference by 24 to get hours as a number. For durations above 24 hours, format the cell as `[h]:mm`.

:::warning
Dates typed as text (`"10/03/2026"` left-aligned) are not dates. The same text can also mean 10 March or 3 October depending on the computer's regional settings. Use `DATE(year, month, day)` for dates you build in formulas, and `DATEVALUE` to convert text dates.
:::

:::tip
`TODAY()` changes every day, so a report using it changes when you reopen the file. For a fixed record (an invoice date), enter the date as a value with **Ctrl + ;**.
:::
