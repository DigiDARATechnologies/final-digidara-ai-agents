---
title: Arrays and the two-pointer pattern
summary: Work with arrays and solve many problems with two pointers moving through the data.
takeaways:
- Arrays give O(1) access by index but costly insertion in the middle
- Two pointers use two indexes to avoid a nested loop
- Works well on sorted data and for in-place changes
---
## Arrays

An **array** (a Python **list**) stores items one after another in memory. Reading `a[i]` is O(1). Inserting or deleting in the middle shifts the items after it, so that is O(n).

## The two-pointer idea

Instead of checking every pair with two loops (O(n squared)), place a pointer at each end (or both at the start) and move them intelligently. Often the work becomes O(n).

## Example 1: pair with a target sum (sorted array)

```python
def pair_with_sum(nums, target):
    left, right = 0, len(nums) - 1
    while left < right:
        current = nums[left] + nums[right]
        if current == target:
            return nums[left], nums[right]
        if current < target:
            left += 1          # need a bigger sum
        else:
            right -= 1         # need a smaller sum
    return None

print(pair_with_sum([1, 3, 4, 6, 8, 11], 10))
print(pair_with_sum([1, 3, 4, 6, 8, 11], 100))
```

```output
(4, 6)
None
```

Because the array is **sorted**, if the sum is too small, only moving `left` right can help; if too big, only moving `right` left can help. One pass, **O(n)** time, **O(1)** space.

## Example 2: reverse in place

```python
def reverse(items):
    left, right = 0, len(items) - 1
    while left < right:
        items[left], items[right] = items[right], items[left]
        left += 1
        right -= 1
    return items

print(reverse([1, 2, 3, 4, 5]))
```

```output
[5, 4, 3, 2, 1]
```

## Example 3: remove duplicates from a sorted array in place

A **slow** pointer marks where to write, a **fast** pointer scans.

```python
def remove_duplicates(nums):
    if not nums:
        return 0
    write = 1
    for read in range(1, len(nums)):
        if nums[read] != nums[read - 1]:
            nums[write] = nums[read]
            write += 1
    return write

data = [1, 1, 2, 2, 2, 3, 4, 4]
k = remove_duplicates(data)
print(k, data[:k])
```

```output
4 [1, 2, 3, 4]
```

## Example 4: move zeros to the end

```python
def move_zeros(nums):
    write = 0
    for read in range(len(nums)):
        if nums[read] != 0:
            nums[write], nums[read] = nums[read], nums[write]
            write += 1
    return nums

print(move_zeros([0, 1, 0, 3, 12]))
```

```output
[1, 3, 12, 0, 0]
```

## When to think "two pointers"

- the array is **sorted**, or you may sort it
- you look for a **pair or triplet** with a condition
- you must change the array **in place**
- you compare **both ends** (palindromes)

:::tip
For three numbers that add to a target: sort, fix one number with a loop, then use two pointers on the rest. That is O(n squared), better than O(n cubed).
:::
