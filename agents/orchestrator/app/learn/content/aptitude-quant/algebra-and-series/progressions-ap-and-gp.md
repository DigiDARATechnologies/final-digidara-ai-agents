---
title: Progressions: AP and GP
summary: Find terms and sums of arithmetic and geometric progressions, and count terms in a list.
takeaways:
- AP adds the same number each time; GP multiplies by the same number
- nth term of AP = a + (n - 1)d; sum = n/2 x (first + last)
- Infinite GP with |r| < 1 has sum a / (1 - r)
---
## Arithmetic progression (AP)

Each term is the previous one **plus a constant d** (common difference): 3, 7, 11, 15, ...

:::formula
nth term = a + (n - 1) d
Sum of n terms = n / 2 x [2a + (n - 1) d] = n / 2 x (first + last)
:::

:::example Term and sum
For the AP 3, 7, 11, ... find the 20th term and the sum of the first 20 terms.

**Solution.** a = 3, d = 4. 20th term = 3 + 19 x 4 = **79**. Sum = 20 / 2 x (3 + 79) = 10 x 82 = **820**.
:::

:::example Counting the terms
How many terms are in 5, 9, 13, ..., 101?

**Solution.** n = (last - first) / d + 1 = (101 - 5) / 4 + 1 = 24 + 1 = **25**.
:::

:::example Multiples
What is the sum of all multiples of 7 up to 100?

**Solution.** The terms are 7, 14, ..., 98: n = 98 / 7 = 14. Sum = 14 / 2 x (7 + 98) = 7 x 105 = **735**.
:::

:::trick
For three numbers in AP, call them a - d, a, a + d. For five, a - 2d, a - d, a, a + d, a + 2d. Their sum is simple.
:::

## Geometric progression (GP)

Each term is the previous one **times a constant r** (common ratio): 2, 6, 18, 54, ...

:::formula
nth term = a x r to the power (n - 1)
Sum of n terms = a (r to the power n - 1) / (r - 1)   (when r is not 1)
Sum to infinity = a / (1 - r)   (only when -1 < r < 1)
:::

:::example Term and sum
For the GP 2, 6, 18, ... find the 6th term and the sum of the first 5 terms.

**Solution.** a = 2, r = 3. 6th term = 2 x 3 to the power 5 = 2 x 243 = **486**. Sum of 5 = 2 x (243 - 1) / 2 = **242**.
:::

:::example Infinite GP
Find the sum of 8 + 4 + 2 + 1 + ... to infinity.

**Solution.** a = 8, r = 1/2. Sum = 8 / (1 - 1/2) = **16**.
:::

## Spotting which one

| Pattern | Type |
| --- | --- |
| differences between terms are equal | AP |
| ratios between terms are equal | GP |
| neither | check the series lesson for other patterns |

## Where it appears

- **Savings that grow by a fixed amount** each month (AP).
- **Compound interest** and population growth (GP).
- **Bouncing ball** problems (GP).

:::example Salary
A person's salary is 30,000 in the first year and rises by 2,000 each year. What is the total earned in 10 years?

**Solution.** a = 30,000, d = 2,000, n = 10. Last = 30,000 + 9 x 2,000 = 48,000. Sum = 10 / 2 x (30,000 + 48,000) = 5 x 78,000 = **3,90,000**.
:::
