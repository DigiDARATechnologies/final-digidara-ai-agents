---
title: Number series
summary: Find the rule behind a series by looking at differences, multiples, squares, alternating patterns and primes.
takeaways:
- Check the differences first, then the ratios
- Look for squares, cubes, primes and Fibonacci
- Two interleaved series alternate their rules
---
## What the question asks

You are given a few numbers and must find the next one. The trick is to ask one question at a time:

1. Is it going **up by the same amount** (add or subtract)?
2. Is it **multiplying** by the same number?
3. Do the **differences** form their own pattern?
4. Are they **squares, cubes or primes**?
5. Are two series **mixed together**?

## Pattern 1: constant difference

:::example Add the same amount
2, 5, 8, 11, ?

**Solution.** Each term is 3 more than the last. Next = **14**.
:::

## Pattern 2: constant multiplier

:::example Multiply
3, 6, 12, 24, ?

**Solution.** Each term is double the last. Next = **48**.
:::

## Pattern 3: growing differences

:::example Differences that grow
1, 2, 4, 7, 11, ?

**Solution.** The differences are 1, 2, 3, 4, so the next difference is 5. Next = 11 + 5 = **16**.
:::

## Pattern 4: squares, cubes and similar

| Series | Rule |
| --- | --- |
| 1, 4, 9, 16, 25 | squares (n²) |
| 1, 8, 27, 64, 125 | cubes (n³) |
| 2, 6, 12, 20, 30, 42 | n × (n + 1) |
| 2, 3, 5, 7, 11, 13 | primes |
| 1, 1, 2, 3, 5, 8, 13 | Fibonacci: each term is the sum of the two before |

:::example Product of neighbours
2, 6, 12, 20, 30, ?

**Solution.** 1×2, 2×3, 3×4, 4×5, 5×6, so the next is 6×7 = **42**.
:::

## Pattern 5: two rules in turn

When the numbers go up and down, try a **different rule for odd and even positions**, or a rule that alternates.

:::example Alternating rules
5, 10, 8, 16, 14, 28, ?

**Solution.** The rule alternates ×2 then −2: 5×2 = 10, 10−2 = 8, 8×2 = 16, 16−2 = 14, 14×2 = 28, 28−2 = **26**.
:::

:::trick
Spend at most 30 seconds writing the differences between neighbours. If they look random, try the ratios, then squares. Most test series use one of the patterns on this page.
:::

:::remember
Before answering, **check the rule on every term you were given**, not only the last two.
:::

:::practice aptitude
Series questions get faster with practice. Try the logical set in the Aptitude Trainer.
:::
