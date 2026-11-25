---
title: Probability
summary: Compute probabilities for coins, dice, cards and bags, including the 'at least one' trick and events without replacement.
takeaways:
- Probability = favourable outcomes / total outcomes
- For independent events multiply; for 'or' with no overlap, add
- P(at least one) = 1 - P(none)
---
## Basics

:::formula
P(event) = favourable outcomes / total outcomes   (a number from 0 to 1)
P(not A) = 1 - P(A)
P(A or B) = P(A) + P(B) - P(A and B)
Independent events: P(A and B) = P(A) x P(B)
:::

## Coins

:::example
A coin is tossed 3 times. What is the probability of at least 2 heads?

**Solution.** Total outcomes = 8. At least two heads: HHH, HHT, HTH, THH = 4. Probability = 4/8 = **1/2**.
:::

## Dice

:::example Sum of two dice
Two dice are rolled. Probability that the sum is 8?

**Solution.** Total = 36. Favourable: (2, 6), (3, 5), (4, 4), (5, 3), (6, 2) = 5. Probability = **5/36**.
:::

:::example At least one six
A die is rolled twice. Probability of getting at least one 6?

**Solution.** P(no six in either) = 5/6 x 5/6 = 25/36. So P(at least one) = 1 - 25/36 = **11/36**.
:::

## Cards

A deck has 52 cards: 4 suits of 13 (26 red, 26 black), 12 face cards, 4 kings.

:::example King or heart
One card is drawn. Probability that it is a king or a heart?

**Solution.** Kings = 4, hearts = 13, and the king of hearts is counted twice. Favourable = 4 + 13 - 1 = 16. Probability = 16/52 = **4/13**.
:::

## Without replacement

:::example Two red balls
A bag has 5 red and 3 blue balls. Two are drawn one after the other without replacement. Probability both are red?

**Solution.** 5/8 x 4/7 = 20/56 = **5/14**.
:::

## Using combinations

:::example
Two balls are drawn together from the same bag (5 red, 3 blue). Probability both are red?

**Solution.** 5C2 / 8C2 = 10 / 28 = **5/14**. Same answer.
:::

:::trick
When the question says "at least one", calculate the **opposite** (none) and subtract from 1. It is almost always shorter.
:::
