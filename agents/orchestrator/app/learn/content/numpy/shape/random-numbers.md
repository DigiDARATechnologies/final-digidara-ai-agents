---
title: Random numbers
summary: Generate random data with the Generator, repeat results with a seed, shuffle and sample.
takeaways:
- Use np.random.default_rng(seed) to get a random generator
- The same seed gives the same numbers every time
- The generator offers uniform, normal, integers, choice and shuffle
---
## The Generator

Random numbers drive simulations, sampling, and splitting data for machine learning. The modern way is to create a **generator** once:

```python
import numpy as np

rng = np.random.default_rng(42)       # 42 is the "seed"
print(rng.random(3))                   # 3 numbers between 0 and 1
```

```output
[0.77395605 0.43887844 0.85859792]
```

## Why the seed matters

A seed makes the "random" sequence **repeatable**. Two generators with the same seed give identical numbers. This lets you reproduce an experiment, or debug it.

```python
a = np.random.default_rng(7).integers(0, 100, size=5)
b = np.random.default_rng(7).integers(0, 100, size=5)
print(a, b, (a == b).all())
```

```output
[94 62 68 89 57] [94 62 68 89 57] True
```

## The common functions

```python
rng = np.random.default_rng(1)

print(rng.integers(1, 7, size=10))             # ten dice rolls (1 to 6)
print(rng.normal(loc=50, scale=10, size=4).round(1))   # bell curve: mean 50, spread 10
print(rng.uniform(0, 1, size=3).round(3))      # every value equally likely
```

```output
[3 4 5 6 1 1 5 6 2 2]
[54.5 44.6 55.8 53.6]
[0.028 0.754 0.538]
```

| Method | What it gives |
| --- | --- |
| `random(n)` | numbers from 0 up to (not including) 1 |
| `integers(a, b, size)` | whole numbers from a up to (not including) b |
| `normal(mean, std, size)` | numbers that follow a bell curve |
| `uniform(a, b, size)` | numbers spread evenly between a and b |
| `choice(items, size)` | a random pick from a list |
| `shuffle(array)` | mixes an array in place |

## Choosing and shuffling

```python
rng = np.random.default_rng(3)
students = np.array(["Asha", "Ravi", "Meena", "Kiran", "Divya", "Arun"])

print(rng.choice(students, size=2, replace=False))     # 2 different students
shuffled = students.copy()
rng.shuffle(shuffled)
print(shuffled)
```

```output
['Asha' 'Divya']
['Kiran' 'Asha' 'Meena' 'Ravi' 'Divya' 'Arun']
```

## A simulation: is the coin fair?

Flip a fair coin 1,000 times and count the heads:

```python
rng = np.random.default_rng(10)
flips = rng.integers(0, 2, size=1000)       # 0 = tails, 1 = heads
print("heads:", flips.sum(), " share:", flips.mean())
```

```output
heads: 484  share: 0.484
```

You get close to 50% but rarely exactly 50%. That small random variation is exactly what statistics measures.

## Splitting data at random

```python
rng = np.random.default_rng(0)
indexes = rng.permutation(10)
train, test = indexes[:7], indexes[7:]
print(train, test)
```

```output
[4 6 2 7 3 5 9] [0 8 1]
```

:::tip
Always set a seed when you split data or run an experiment you may want to repeat. Print it in your notebook so others can reproduce your numbers.
:::

:::note
You may see `np.random.seed(42)` and `np.random.rand()` in older tutorials. They still work, but `default_rng` is the recommended modern approach.
:::
