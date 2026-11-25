---
title: Calendars and days of the week
summary: Find the day of the week for any date using odd days, and handle leap years.
takeaways:
- Odd days are the remainder when days are divided by 7
- An ordinary year has 1 odd day, a leap year has 2
- 100 years have 5 odd days, 200 have 3, 300 have 1 and 400 have 0
---
## Odd days

A week has 7 days, so we only care about the **remainder** when the number of days is divided by 7. That remainder is the number of **odd days**.

| Period | Odd days |
| --- | --- |
| Ordinary year (365 days) | 1 |
| Leap year (366 days) | 2 |
| 100 years | 5 |
| 200 years | 3 |
| 300 years | 1 |
| 400 years | 0 |

Day code: **0 = Sunday, 1 = Monday, 2 = Tuesday, 3 = Wednesday, 4 = Thursday, 5 = Friday, 6 = Saturday.**

## Leap years

A year is a leap year if it is divisible by 4, **except** century years, which must be divisible by **400**.

- 2024 is a leap year. 1900 is not. 2000 is.

## Months

Days: Jan 31, Feb 28 or 29, Mar 31, Apr 30, May 31, Jun 30, Jul 31, Aug 31, Sep 30, Oct 31, Nov 30, Dec 31. Odd days of months: 31-day months give 3 odd days, 30-day months give 2, February gives 0 (or 1 in a leap year).

## Finding the day of a date

:::example 15 August 1947
**Solution.**
- 1600 years: 0 odd days. Next 300 years (1601 to 1900): 1 odd day.
- 46 years (1901 to 1946): 11 leap years (1904, ..., 1944) and 35 ordinary years: 11 x 2 + 35 x 1 = 57, and 57 divided by 7 leaves 1 odd day.
- So 31 December 1946 gives 1 + 1 = 2 odd days: a **Tuesday**.
- From 1 January to 15 August 1947: 31 + 28 + 31 + 30 + 31 + 30 + 31 = 212 days up to 31 July, plus 15 = 227 days. 227 divided by 7 leaves 3.
- Total odd days = 2 + 3 = 5, which is **Friday**.
:::

## Easier: from a known date

:::example Same month
If 5 March is a Monday, what day is 20 March?

**Solution.** The gap is 15 days. 15 divided by 7 leaves 1. Monday + 1 = **Tuesday**.
:::

:::example Next year
If 1 January 2026 is a Thursday, what day is 1 January 2027?

**Solution.** 2026 is an ordinary year (1 odd day). Thursday + 1 = **Friday**.
:::

## Counting days

:::example
How many Sundays are there in a 31-day month that starts on a Sunday?

**Solution.** 31 days = 4 weeks + 3 extra days. The extra days are Sunday, Monday, Tuesday, so there are **5 Sundays**.
:::

:::trick
For a month of 28 days every day appears 4 times. For 30 days, the first 2 weekdays appear 5 times. For 31 days, the first 3 weekdays appear 5 times.
:::
