---
title: Dice and cubes
summary: Solve questions on opposite faces of a dice and on painted cubes cut into smaller cubes.
takeaways:
- On a standard die, opposite faces add to 7
- A painted cube cut into n x n x n small cubes has 8 corners with three painted faces
- Use the formulas for 3-face, 2-face, 1-face and 0-face cubes
---
## Dice

On a standard die the **opposite faces add up to 7**: 1 is opposite 6, 2 is opposite 5, 3 is opposite 4. Any two faces that touch (are adjacent) are never opposite.

:::example Opposite face
A die shows 2 on the top. What is on the bottom?

**Solution.** 7 - 2 = **5**.
:::

:::example Three faces visible
A die is shown with 1, 2 and 3 on three visible faces. What are on the faces opposite to these?

**Solution.** The opposite faces are 6, 5 and 4.
:::

If two pictures of the same die are given, find the common face and use the rotation direction to find the unknown faces.

## Painted cube cut into small cubes

A big cube is painted on all faces and cut into n x n x n small cubes of equal size.

| Cubes with | Formula | n = 3 | n = 4 | n = 5 |
| --- | --- | --- | --- | --- |
| **3 faces** painted (corners) | 8 | 8 | 8 | 8 |
| **2 faces** painted (edges) | 12 (n - 2) | 12 | 24 | 36 |
| **1 face** painted (face centres) | 6 (n - 2) squared | 6 | 24 | 54 |
| **0 faces** (inside) | (n - 2) cubed | 1 | 8 | 27 |
| **Total** | n cubed | 27 | 64 | 125 |

:::example
A cube painted on all sides is cut into 64 equal small cubes. How many have exactly two faces painted?

**Solution.** 64 = 4 cubed, so n = 4. Two faces painted = 12 x (4 - 2) = **24**.
:::

:::example Unpainted
How many of the 125 small cubes (n = 5) have no paint?

**Solution.** (5 - 2) cubed = **27**.
:::

## Cubes painted with different colours

If the top and bottom are painted red and the four sides blue, count by position: the corner cubes have one red and two blue faces, and so on. Draw the cube and count layer by layer.

## Cutting a cuboid

A 4 x 3 x 2 cuboid cut into 1 unit cubes gives 4 x 3 x 2 = 24 cubes. The number of cuts needed along each side is one less than the number of pieces along that side.

:::trick
Remember the 8 / 12(n - 2) / 6(n - 2) squared / (n - 2) cubed pattern. It answers almost every painted-cube question in a few seconds.
:::
