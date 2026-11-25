---
title: Number system and divisibility
summary: Learn the types of numbers, quick divisibility tests, unit digits, number of factors and remainders.
takeaways:
- Use divisibility rules to test a number without dividing
- Unit digits of powers repeat in short cycles
- The number of factors comes from the prime factorisation
---
## Types of numbers

| Type | Examples |
| --- | --- |
| Natural | 1, 2, 3, ... |
| Whole | 0, 1, 2, ... |
| Integers | ..., -2, -1, 0, 1, 2, ... |
| Prime | 2, 3, 5, 7, 11, 13, 17, 19 (exactly two factors) |
| Composite | 4, 6, 8, 9, 10 ... (more than two factors) |
| Rational | numbers that can be written as a fraction p/q |

1 is neither prime nor composite. **2 is the only even prime.**

## Divisibility rules

| Divisor | Rule |
| --- | --- |
| 2 | last digit is even |
| 3 | sum of digits is divisible by 3 |
| 4 | last two digits divisible by 4 |
| 5 | last digit is 0 or 5 |
| 6 | divisible by both 2 and 3 |
| 8 | last three digits divisible by 8 |
| 9 | sum of digits is divisible by 9 |
| 10 | last digit is 0 |
| 11 | (sum of digits at odd places) minus (sum at even places) is 0 or a multiple of 11 |

:::example Test 11
Is 7832 divisible by 11?

**Solution.** Digits 7, 8, 3, 2. Odd places: 7 + 3 = 10. Even places: 8 + 2 = 10. Difference = 0, so **yes** (7832 = 11 x 712).
:::

## Unit digit of a power

The last digit of powers repeats in a **cycle**.

| Last digit | Cycle | Length |
| --- | --- | --- |
| 2 | 2, 4, 8, 6 | 4 |
| 3 | 3, 9, 7, 1 | 4 |
| 7 | 7, 9, 3, 1 | 4 |
| 8 | 8, 4, 2, 6 | 4 |
| 4, 9 | 4, 6 and 9, 1 | 2 |
| 0, 1, 5, 6 | stays the same | 1 |

:::example Unit digit
Find the unit digit of 7^123.

**Solution.** The cycle for 7 has length 4. 123 divided by 4 leaves remainder 3, so take the 3rd number in the cycle (7, 9, 3, 1) = **3**.
:::

## Number of factors

Write the number as a product of primes: N = a^p x b^q x c^r. The number of factors is (p + 1)(q + 1)(r + 1).

:::example Count the factors
How many factors does 360 have?

**Solution.** 360 = 2^3 x 3^2 x 5^1. Factors = (3 + 1)(2 + 1)(1 + 1) = 4 x 3 x 2 = **24**.
:::

## Useful sums

:::formula
Sum of first n natural numbers = n(n + 1) / 2
Sum of first n odd numbers = n squared
Sum of first n even numbers = n(n + 1)
:::

The sum of the first 50 natural numbers is 50 x 51 / 2 = **1275**.

## Remainders

:::example Make it divisible
What is the smallest number to add to 1000 so that it is divisible by 7?

**Solution.** 1000 = 7 x 142 + 6. Remainder 6, so add 7 - 6 = **1** (1001 = 7 x 143).
:::

:::trick
A number is divisible by 6 only if it passes **both** tests (2 and 3). Combine rules for composite divisors: 12 = 3 and 4, 15 = 3 and 5.
:::
