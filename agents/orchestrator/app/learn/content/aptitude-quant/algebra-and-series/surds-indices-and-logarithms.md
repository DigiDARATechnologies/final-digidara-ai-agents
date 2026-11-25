---
title: Surds, indices and logarithms
summary: Use the laws of exponents, simplify and rationalise surds, and apply the basic laws of logarithms.
takeaways:
- Same base: add the powers when multiplying, subtract when dividing
- Rationalise a surd by multiplying with its conjugate
- A logarithm is the power: log base a of b = c means a to the power c = b
---
## Laws of indices

:::formula
a^m x a^n = a^(m + n)       a^m / a^n = a^(m - n)
(a^m)^n = a^(mn)            (ab)^n = a^n b^n
a^0 = 1                     a^(-n) = 1 / a^n
a^(1/n) = the nth root of a
:::

:::example Powers
Simplify 2^10 / 2^7.

**Solution.** 2^(10 - 7) = 2^3 = **8**.
:::

:::example Fractional power
Find 27^(2/3).

**Solution.** The cube root of 27 is 3, and 3 squared = **9**.
:::

:::example Solve for x
If 2^(x + 1) = 32, find x.

**Solution.** 32 = 2^5, so x + 1 = 5 and x = **4**.
:::

## Surds

A **surd** is a root that cannot be simplified to a whole number, like sqrt(2) or sqrt(3).

- sqrt(a) x sqrt(b) = sqrt(ab)
- sqrt(12) = sqrt(4 x 3) = **2 sqrt(3)**

### Rationalising

Remove a surd from the denominator by multiplying the top and bottom by the **conjugate** (same terms, opposite sign).

:::example
Rationalise 1 / (sqrt(3) - 1).

**Solution.** Multiply by (sqrt(3) + 1) / (sqrt(3) + 1). The denominator becomes 3 - 1 = 2. Result: **(sqrt(3) + 1) / 2**.
:::

:::example Product with conjugate
Find (sqrt(5) + sqrt(3))(sqrt(5) - sqrt(3)).

**Solution.** It is a difference of squares: 5 - 3 = **2**.
:::

### Comparing surds

Raise both to a common power so the roots disappear.

:::example Which is larger
Which is larger: the square root of 2 or the cube root of 3?

**Solution.** Raise both to the power 6. (sqrt 2)^6 = 2^3 = 8 and (cube root of 3)^6 = 3^2 = 9. Since 9 is greater, the **cube root of 3 is larger**.
:::

## Logarithms

:::formula
log base a of b = c  means  a^c = b
log(mn) = log m + log n      log(m / n) = log m - log n
log(m^n) = n log m           log base a of a = 1,  log of 1 = 0
:::

:::example Meaning
Find log base 2 of 8.

**Solution.** 2^3 = 8, so the answer is **3**.
:::

:::example Using the laws
Given log 2 = 0.3010, find log 8.

**Solution.** log 8 = log (2^3) = 3 x 0.3010 = **0.9030**.
:::

:::example Digits in a number
How many digits does 2^20 have? (log 2 = 0.3010)

**Solution.** log (2^20) = 20 x 0.3010 = 6.02. The number of digits is the integer part plus 1 = **7** (2^20 = 1,048,576).
:::

:::remember
"Common log" means base 10, so log 100 = 2 and log 1000 = 3.
:::
