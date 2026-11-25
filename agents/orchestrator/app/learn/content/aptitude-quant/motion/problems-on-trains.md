---
title: Problems on trains
summary: Handle trains crossing poles, platforms and each other, with unit conversion between km/h and m/s.
takeaways:
- km/h to m/s: multiply by 5/18; m/s to km/h: multiply by 18/5
- Crossing a pole means covering its own length; crossing a platform means length plus platform
- Opposite directions add speeds; same direction subtracts them
---
## Unit conversion

:::formula
km/h to m/s: multiply by **5/18**.   m/s to km/h: multiply by **18/5**.
Time = distance / speed
:::

54 km/h = 54 x 5/18 = **15 m/s**. 72 km/h = **20 m/s**.

## A train crossing a pole or a person

The distance is just the **length of the train**.

:::example
A 150 m train runs at 54 km/h. How long to cross a pole?

**Solution.** 54 km/h = 15 m/s. Time = 150 / 15 = **10 seconds**.
:::

## Crossing a platform or bridge

Distance = length of train + length of platform.

:::example
A 200 m train at 72 km/h crosses a 300 m platform. How long does it take?

**Solution.** 72 km/h = 20 m/s. Time = (200 + 300) / 20 = **25 seconds**.
:::

## Two trains

| Direction | Relative speed |
| --- | --- |
| opposite | **sum** of speeds |
| same | **difference** of speeds |

The distance to cover is the **sum of the two lengths**.

:::example Opposite directions
Trains of length 120 m and 180 m run at 60 and 40 km/h towards each other. In how many seconds do they cross?

**Solution.** Relative speed = 100 km/h = 100 x 5/18 = 250/9 m/s. Distance = 300 m. Time = 300 / (250/9) = **10.8 seconds**.
:::

:::example Same direction
The same two trains run in the same direction. How long for the faster (60 km/h) to completely pass the slower (40 km/h)?

**Solution.** Relative speed = 20 km/h = 50/9 m/s. Time = 300 / (50/9) = **54 seconds**.
:::

:::trick
When a train crosses a platform in time t1 and a pole in time t2, its length / platform length ratio is t2 : (t1 - t2).
:::
