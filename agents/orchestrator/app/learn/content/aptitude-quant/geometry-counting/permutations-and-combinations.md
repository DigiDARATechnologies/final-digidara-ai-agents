---
title: Permutations and combinations
summary: Count arrangements and selections: factorials, nPr, nCr, repeated letters and circular arrangements.
takeaways:
- Permutation: order matters. Combination: order does not matter
- nPr = n! / (n - r)!   nCr = n! / (r!(n - r)!)
- For 'at least one' questions, subtract the opposite case from the total
---
## The basic principle

If one task can be done in m ways and another in n ways, doing both can be done in **m x n** ways.

## Factorial

n! = n x (n - 1) x ... x 1, so 5! = 120. By definition 0! = 1.

## Permutations (order matters)

:::formula
nPr = n! / (n - r)!      nCr = n! / (r! (n - r)!)
:::

:::example Arranging books
In how many ways can 5 different books be arranged on a shelf? In how many ways can 3 of them be chosen and arranged?

**Solution.** All five: 5! = **120**. Three of five: 5P3 = 5 x 4 x 3 = **60**.
:::

## Repeated items

:::example Letters of LEADER
How many arrangements of the letters of the word LEADER?

**Solution.** 6 letters with E repeated twice: 6! / 2! = 720 / 2 = **360**.
:::

## Combinations (order does not matter)

:::example Committee
In how many ways can a committee of 3 be chosen from 6 people?

**Solution.** 6C3 = (6 x 5 x 4) / (3 x 2 x 1) = **20**.
:::

:::example At least one woman
A committee of 3 is chosen from 4 men and 3 women. How many committees have at least one woman?

**Solution.** Total = 7C3 = 35. All men = 4C3 = 4. At least one woman = 35 - 4 = **31**.
:::

## Numbers from digits

:::example
How many 3-digit numbers can be formed from the digits 1, 2, 3, 4, 5 without repetition? How many are even?

**Solution.** All: 5P3 = **60**. Even: the units digit must be 2 or 4 (2 ways); then the other two places in 4 x 3 = 12 ways, so 2 x 12 = **24**.
:::

## Circular arrangements

Arranging n people around a round table: **(n - 1)!** ways.

:::example
In how many ways can 5 people sit around a round table?

**Solution.** (5 - 1)! = 4! = **24**.
:::

:::trick
Words like "choose, select, committee, team" mean combinations. Words like "arrange, order, rank, password" mean permutations.
:::
