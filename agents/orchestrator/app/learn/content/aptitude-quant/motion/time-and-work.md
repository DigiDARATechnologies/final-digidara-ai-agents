---
title: Time and work
summary: Combine workers, find a missing worker's time, and solve pipes and cisterns with the one-day rate method.
takeaways:
- If someone finishes in n days, they do 1/n of the work each day
- Add rates when people work together
- Pipes work the same way: inlet adds, outlet subtracts
---
## The one-day rate

If A can do a job in 10 days, in **one day** A does 1/10 of it. This rate is the key to every problem here.

:::formula
Rate = 1 / (days to finish alone)

Together: rate A + rate B

Days together = (a × b) / (a + b)   for two people
:::

:::example Two workers together
A can finish a job in 10 days and B in 15 days. How long will they take together?

**Solution.** Rates: 1/10 + 1/15 = 3/30 + 2/30 = 5/30 = 1/6. So they take **6 days**. Check: (10 × 15) / 25 = 6 ✓.
:::

## The LCM shortcut

Pick a total amount of work that both times divide into, such as the LCM, and count in whole units.

For the same job: total = 30 units. A does 3 units a day, B does 2 units a day, together 5 a day, and 30 / 5 = **6 days**. No fractions needed.

:::example Finding the missing person
A and B together finish a job in 12 days. A alone takes 20 days. How long does B take alone?

**Solution.** B's rate = 1/12 − 1/20 = 5/60 − 3/60 = 2/60 = 1/30. B takes **30 days**.
:::

:::example One leaves early
A can do a job in 20 days and B in 30 days. A works for 4 days and then leaves. How long does B take to finish?

**Solution.** In 4 days A does 4/20 = 1/5. Remaining = 4/5. B does the rest in 4/5 × 30 = **24 days**.
:::

## Men and days

More men means fewer days. The product stays the same.

:::example Building a wall
12 men build a wall in 15 days. How long will 9 men take?

**Solution.** Work = 12 × 15 = 180 man-days. 180 / 9 = **20 days**.
:::

## Pipes and cisterns

A pipe that fills is positive. A pipe that empties is negative.

:::example Inlet and outlet
An inlet fills a tank in 6 hours and an outlet empties it in 9 hours. If both are open, how long to fill the empty tank?

**Solution.** Rate = 1/6 − 1/9 = 3/18 − 2/18 = 1/18. It takes **18 hours**.
:::

:::remember
Never add the **days**. Add the **rates** (work per day), then turn the answer back into days.
:::

:::practice aptitude
Time and work problems repeat in every campus test. Practise them in the Aptitude Trainer.
:::
