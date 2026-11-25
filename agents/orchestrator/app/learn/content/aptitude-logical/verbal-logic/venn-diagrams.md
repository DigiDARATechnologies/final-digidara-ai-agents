---
title: Venn diagrams and set problems
summary: Use circles to show relationships between groups, and count people with the inclusion-exclusion formula.
takeaways:
- Overlapping circles show things that belong to both groups
- n(A or B) = n(A) + n(B) - n(A and B)
- Fill in the overlap first, then the remaining parts
---
## Reading a Venn diagram

Each circle is a group. Overlap means **in both**. Outside all circles means **in none**.

Common relationship pictures:
- **Doctors, Humans:** all doctors are humans, so the Doctors circle is **inside** Humans.
- **Dogs, Cats:** no dog is a cat, so two **separate** circles.
- **Students, Players:** some students play, so two **overlapping** circles.

## The counting formula

:::formula
n(A or B) = n(A) + n(B) - n(A and B)
Neither = Total - n(A or B)
:::

:::example Two sports
In a class of 50 students, 30 play cricket, 25 play football and 10 play both. How many play neither?

**Solution.** Either game = 30 + 25 - 10 = 45. Neither = 50 - 45 = **5**.
:::

:::example Only one
In the same class, how many play **only** cricket?

**Solution.** Only cricket = 30 - 10 = **20**.
:::

## Three groups

:::formula
n(A or B or C) = n(A) + n(B) + n(C) - n(A and B) - n(B and C) - n(A and C) + n(A and B and C)
:::

:::example Languages
In a group, 20 speak English, 15 speak Hindi, 10 speak Tamil. 6 speak English and Hindi, 4 speak Hindi and Tamil, 5 speak English and Tamil, and 2 speak all three. How many speak at least one language?

**Solution.** 20 + 15 + 10 - 6 - 4 - 5 + 2 = **32**.
:::

## Which picture fits?

:::example
Which diagram represents Mother, Woman, Doctor?

**Solution.** All mothers are women, so Mother is **inside** Woman. Some women are doctors and some mothers may be doctors, so the Doctor circle **overlaps both** Woman and Mother.
:::

:::trick
When filling a three-circle diagram, start with the **centre** (all three), then the pairs-only regions, then the single regions, working outward.
:::
