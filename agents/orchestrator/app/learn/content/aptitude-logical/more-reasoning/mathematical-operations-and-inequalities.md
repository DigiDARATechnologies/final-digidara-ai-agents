---
title: Mathematical operations and coded inequalities
summary: Solve questions where symbols are swapped, and read chains of inequality signs to find what must be true.
takeaways:
- First replace the symbols, then follow BODMAS
- In a chain of inequalities, a conclusion holds only if it is true through the whole chain
- Equal signs link, but mixed directions break the link
---
## Symbol substitution

The question tells you that some symbols have new meanings. **Rewrite the expression with the real symbols**, then calculate using BODMAS.

:::example
If + means x, x means -, - means divide, and divide means +, find the value of 12 divide 4 x 3 + 2 - 1.

**Solution.** Replace each symbol with its real operation: "divide" becomes +, "x" becomes -, "+" becomes x, "-" becomes divide.
The expression becomes 12 + 4 - 3 x 2 / 1.
By BODMAS: 3 x 2 / 1 = 6, and 12 + 4 - 6 = **10**.
:::

:::example Swapped numbers
If 3 and 5 are interchanged, what is the value of 3 x 4 + 5?

**Solution.** After swapping: 5 x 4 + 3 = 20 + 3 = **23**.
:::

## Comparison signs

| Sign | Meaning |
| --- | --- |
| > | greater than |
| < | less than |
| >= | greater than or equal to |
| <= | less than or equal to |
| = | equal to |

## Chains of inequalities

Read the chain from left to right. A conclusion between two items is **definitely true** only if all the signs between them point the same way (or are equal signs), and then it is **strict** (greater) if at least one is strict.

:::example
Statement: A > B >= C = D < E

**Conclusions:**
I. A > C
II. B > D
III. E > C
IV. A > E

**Solution.**
- I: A > B >= C, so A > C. **True** (one strict sign).
- II: B >= C = D, so B >= D, but B > D is not certain. **False**.
- III: C = D < E, so C < E, which means E > C. **True**.
- IV: A and E are connected only through the lower items, with mixed directions, so nothing can be said. **False**.

So **I and III** follow.
:::

## Either/or conclusions

If a pair of conclusions is like "X > Y" and "X <= Y", exactly one of them is always true, so **either I or II follows**.

## Coded form

Some questions use symbols such as % for >, # for < and @ for =, and ask which conclusions follow from "P % Q # R @ S". Translate to ordinary signs first: P > Q < R = S. Then Q < R and R = S, so Q < S; P and R cannot be compared.

:::trick
In a chain, two signs pointing **towards** each other (such as > then <) break the link: you cannot compare the items on either side of them.
:::
