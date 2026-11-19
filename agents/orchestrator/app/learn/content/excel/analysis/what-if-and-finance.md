---
title: What-if analysis and finance functions
summary: Test scenarios with Goal Seek, Data Tables and Scenario Manager, and calculate loans, savings and investments with PMT, FV, NPV and IRR.
takeaways:
- Goal Seek finds the input that gives a target result; Data Tables show many inputs at once
- PMT, FV, PV, NPER and RATE handle loans and savings
- NPV and IRR judge whether an investment is worthwhile
---
## What-if analysis

A model is a set of inputs, formulas and outputs. **What-if analysis** changes the inputs to see how the output responds: "What if interest rises by 1%? How much must I sell to reach the target?"

Good habit: keep every input (rate, years, price) in **its own labelled cell**, never typed inside formulas, so you can change one cell and see everything update.

## Loan EMI with PMT

`=PMT(rate_per_period, number_of_periods, -loan_amount)`

For a loan of ₹10,00,000 at 9% a year for 5 years, paid monthly:



| Cell | Formula | Result |
| --- | --- | --- |
| EMI per month | `=PMT(B2/12,B3*12,-B1)` | about **₹20,758** |
| total paid | `=B5*B3*12` | about ₹12,45,498 |
| total interest | `=B6-B1` | about ₹2,45,498 |

Remember to **convert** the yearly rate to monthly (`/12`) and the years to months (`*12`). The loan amount is negative so that the payment appears as a positive number; Excel's sign convention treats money you receive and money you pay as opposite signs.

Related functions:

| Function | Answers |
| --- | --- |
| `PMT(rate, nper, pv)` | the regular payment |
| `IPMT`, `PPMT` | the interest part and the principal part of one payment |
| `NPER(rate, pmt, pv)` | how many payments are needed |
| `RATE(nper, pmt, pv)` | the interest rate per period |
| `PV(rate, nper, pmt)` | what a stream of payments is worth today |
| `FV(rate, nper, pmt)` | what regular savings grow to |

## Saving regularly with FV

Saving ₹5,000 every month for 10 years at 8% a year:



`=FV(0.08/12,10*12,-5000)` is about **₹9,14,734**, while the total you paid in is ₹6,00,000: the difference is growth from compound interest.

## Compound growth



₹1,000 at 10% for 5 years grows to **₹1,610.51**. And money that doubled in 5 years grew by about **14.87%** a year: `=(end/start)^(1/years)-1` is the formula for CAGR (compound annual growth rate).

## NPV and IRR: is the investment worth it?

A project costs ₹1,00,000 now and returns ₹40,000, ₹50,000 and ₹60,000 over three years. With a required return of 10%:



| Formula | Result | Meaning |
| --- | --- | --- |
| `=NPV(0.1,A2:A4)+A1` | about ₹22,765 | value today of the returns minus the cost; positive means worthwhile |
| `=IRR(A1:A4)` | about 21.6% | the rate at which the project breaks even |

`NPV` assumes the **first cash flow is one period away**, so the initial investment (today) is added **outside** the function (`+A1`). A positive NPV (or an IRR above your required return) means the project earns more than you need.

## Goal Seek

**Data, What-If Analysis, Goal Seek** works backwards: "I want this formula cell to reach a value; which input cell should change?"

Example: you can afford an EMI of ₹15,000. What loan amount is that? Set the EMI cell to 15,000 by changing the loan amount cell. Goal Seek adjusts the input until the formula gives the target.

You can check the answer directly with `PV`:



A ₹15,000 monthly EMI at 9% over 5 years supports a loan of about **₹7,22,580**. Goal Seek would reach the same answer by trial and adjustment.

## Data Tables, Scenarios and Solver

| Tool | Use |
| --- | --- |
| **Data Table** (one or two inputs) | see the EMI for every combination of rate and years in a grid |
| **Scenario Manager** | store named sets of inputs ("Best case", "Worst case") and switch between them |
| **Solver** (add-in) | find the best mix under limits, such as the product mix with maximum profit |

:::warning
A model is only as good as its assumptions. Label inputs clearly, colour input cells (for example blue text), keep formulas free of hard-coded numbers, and show a base, a best and a worst case before trusting one answer.
:::
