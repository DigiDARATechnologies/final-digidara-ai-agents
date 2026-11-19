---
title: NumPy interview questions
summary: The NumPy questions fresher data and ML interviews ask, with short answers.
kind: qa
takeaways:
- Be ready to explain why NumPy is faster than lists
- Know broadcasting, views versus copies and the axis argument
- Practise explaining reshape and boolean masks
---
### Q [Easy] What is NumPy and why use it instead of Python lists?
NumPy is a library for fast numerical computing. Its arrays hold items of one type in contiguous memory and support **vectorised** operations in compiled code, so they use less memory and run much faster than looping over lists.

### Q [Easy] What is the difference between a list and a NumPy array?
A list can hold mixed types and is flexible but slow for maths. An array holds one type, supports element-wise maths without loops, and has a fixed shape. Adding two lists joins them, while adding two arrays adds item by item.

### Q [Easy] What are `shape`, `ndim`, `size` and `dtype`?
`shape` is the size of each dimension, `ndim` is the number of dimensions, `size` is the total number of items, and `dtype` is the data type of the items.

### Q [Medium] What is broadcasting?
The rule that lets NumPy do arithmetic on arrays of **different shapes** by stretching the smaller one. Shapes are compared from the right, and two sizes are compatible when they are equal or one of them is 1.

### Q [Medium] What is the difference between a view and a copy?
A **view** shares memory with the original array, so changing one changes the other (slices return views). A **copy** is independent. Use `.copy()` when you need a separate array.

### Q [Easy] What does `axis` mean in `sum`, `mean` and similar functions?
It is the axis the operation runs along. For a 2D array, `axis=0` gives one result per column (operating down the rows), and `axis=1` gives one result per row.

### Q [Medium] What is the difference between `reshape` and `resize`?
`reshape` returns an array with a new shape and needs the same number of items. `resize` can change the number of items (padding or cutting), and the in-place version modifies the array itself.

### Q [Medium] What is the difference between `flatten` and `ravel`?
Both make a 1D array. `flatten` always returns a **copy**. `ravel` returns a **view** when it can, which is faster.

### Q [Medium] How do you filter values in an array?
With a boolean mask: `a[a > 5]`. Combine conditions with `&` and `|` and brackets: `a[(a > 5) & (a < 10)]`.

### Q [Medium] What is the difference between `np.arange` and `np.linspace`?
`arange(start, stop, step)` makes values by step size and excludes the end. `linspace(start, stop, num)` gives a chosen **number** of evenly spaced points and includes the end by default.

### Q [Medium] How is `*` different from `@` and `np.dot`?
`*` is element-wise multiplication. `@` (and `np.dot` for 2D arrays) is matrix multiplication.

### Q [Hard] Why is vectorised code faster than a Python loop?
A Python loop runs the interpreter for each item, with type checks every time. NumPy runs one compiled loop in C over data of one known type stored contiguously, and can use CPU features like SIMD.

### Q [Medium] How do you make random numbers repeatable?
Create the generator with a seed, `rng = np.random.default_rng(42)`. The same seed gives the same sequence every time.

### Q [Medium] How do you find the position of the maximum value?
`np.argmax(a)`, or `a.argmax()`. For a 2D array use the `axis` argument to find it per row or column.

:::practice mock-interview
Practise explaining broadcasting and views aloud in a Mock Interview.
:::
