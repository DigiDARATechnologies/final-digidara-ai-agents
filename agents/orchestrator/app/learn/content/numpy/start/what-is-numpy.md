---
title: What is NumPy?
summary: NumPy gives Python fast arrays and maths on whole arrays at once. It is the base of Pandas, scikit-learn and most data tools.
takeaways:
- A NumPy array stores numbers of one type in a compact block
- Operations work on the whole array at once, with no loop
- Pandas, scikit-learn and Matplotlib are all built on NumPy
---
## Why not just use a list?

A Python list can hold anything, which makes it flexible and slow. For millions of numbers you want something stricter and faster. **NumPy** (Numerical Python) gives you the **array**: a grid of numbers that all have the same type, stored together in memory.

| | Python list | NumPy array |
| --- | --- | --- |
| Holds | anything | numbers of one type |
| Maths on all items | needs a loop | one expression |
| Speed on big data | slow | 10 to 100 times faster |
| Memory | larger | compact |

```py
pip install numpy
```

By convention, import it as `np`:

```python
import numpy as np

print(np.__version__ >= "1.20")
```

```output
True
```

## Your first array

```python
marks = np.array([92, 78, 85, 66, 88])
print(marks)
print(type(marks), marks.dtype, marks.shape)
```

```output
[92 78 85 66 88]
<class 'numpy.ndarray'> int32 (5,)
```

## Maths without a loop

With a list you need a loop to add 5 to every item. With an array you write the maths once:

```python
print(marks + 5)
print(marks * 2)
print(marks / 100)
```

```output
[97 83 90 71 93]
[184 156 170 132 176]
[0.92 0.78 0.85 0.66 0.88]
```

This is called **vectorisation**. It is shorter to write, and it runs in fast compiled code instead of a Python loop.

## A speed test

```python
import time

big = list(range(1_000_000))
arr = np.arange(1_000_000, dtype=np.int64)     # 64-bit integers, so the total cannot overflow

start = time.perf_counter()
total_list = sum(x * 2 for x in big)
list_time = time.perf_counter() - start

start = time.perf_counter()
total_arr = (arr * 2).sum()
arr_time = time.perf_counter() - start

print(total_list == total_arr)
print("array is faster:", arr_time < list_time)
```

```output
True
array is faster: True
```

:::note
The exact timings depend on your computer, so we only check which is faster. On most machines the NumPy version is many times faster.

We asked for `dtype=np.int64` because on Windows NumPy's default integer can be 32-bit, and a total this large would overflow and silently give a wrong answer. NumPy integers have a fixed size, unlike Python's, so keep an eye on `dtype` when numbers get big.
:::

## Where NumPy fits

| Library | What it adds on top of NumPy |
| --- | --- |
| **Pandas** | labelled tables (DataFrames) |
| **scikit-learn** | machine learning models |
| **Matplotlib** | charts |
| **SciPy** | scientific and statistical functions |

:::tip
Learn NumPy first, even briefly. When a Pandas or scikit-learn result looks strange, the cause is often an array shape or type, and NumPy is how you look inside.
:::
