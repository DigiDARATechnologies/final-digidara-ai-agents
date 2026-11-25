---
title: Array and string problems
summary: Six classic array problems with the idea, the code and the complexity: stock profit, product except self, 3Sum, container, rotate and majority.
takeaways:
- Say the brute force, then the improvement
- Most array problems are solved by one pass, two pointers or a running value
- State time and space complexity for every solution
---
For each problem: understand it, say the **brute force**, then find the **improvement**.

## 1. Best time to buy and sell a stock

**Problem.** `prices[i]` is the price on day `i`. Buy once and sell later for the maximum profit.

**Idea.** Track the lowest price so far; at each day the best profit is `price - lowest`.

```python
def max_profit(prices):
    lowest, best = float("inf"), 0
    for price in prices:
        lowest = min(lowest, price)
        best = max(best, price - lowest)
    return best

print(max_profit([7, 1, 5, 3, 6, 4]), max_profit([7, 6, 4, 3, 1]))
```

```output
5 0
```

Time **O(n)**, space **O(1)**.

## 2. Product of array except self

**Problem.** Return an array where each element is the product of all the others, **without division**.

**Idea.** Product of everything to the left times product of everything to the right.

```python
def product_except_self(nums):
    result = [1] * len(nums)
    left = 1
    for i in range(len(nums)):
        result[i] = left
        left *= nums[i]
    right = 1
    for i in range(len(nums) - 1, -1, -1):
        result[i] *= right
        right *= nums[i]
    return result

print(product_except_self([1, 2, 3, 4]))
```

```output
[24, 12, 8, 6]
```

Time **O(n)**, extra space **O(1)** (apart from the output).

## 3. Three Sum

**Problem.** Find all unique triplets that add up to zero.

**Idea.** Sort, fix one number, and use two pointers for the other two. Skip duplicates.

```python
def three_sum(nums):
    nums.sort()
    result = []
    for i in range(len(nums) - 2):
        if i > 0 and nums[i] == nums[i - 1]:
            continue
        left, right = i + 1, len(nums) - 1
        while left < right:
            total = nums[i] + nums[left] + nums[right]
            if total < 0:
                left += 1
            elif total > 0:
                right -= 1
            else:
                result.append([nums[i], nums[left], nums[right]])
                left += 1
                while left < right and nums[left] == nums[left - 1]:
                    left += 1
    return result

print(three_sum([-1, 0, 1, 2, -1, -4]))
```

```output
[[-1, -1, 2], [-1, 0, 1]]
```

Time **O(n squared)**, space O(1) beyond the output.

## 4. Container with most water

**Problem.** Heights `h[i]` are vertical lines. Choose two lines to hold the most water.

**Idea.** Start with the widest pair. The area is limited by the **shorter** line, so move the shorter side inward.

```python
def max_area(height):
    left, right = 0, len(height) - 1
    best = 0
    while left < right:
        best = max(best, min(height[left], height[right]) * (right - left))
        if height[left] < height[right]:
            left += 1
        else:
            right -= 1
    return best

print(max_area([1, 8, 6, 2, 5, 4, 8, 3, 7]))
```

```output
49
```

Time **O(n)**.

## 5. Rotate an array by k

**Idea.** Reverse the whole array, then reverse the first k and the rest.

```python
def rotate(nums, k):
    k %= len(nums)
    def reverse(a, b):
        while a < b:
            nums[a], nums[b] = nums[b], nums[a]
            a += 1
            b -= 1
    reverse(0, len(nums) - 1)
    reverse(0, k - 1)
    reverse(k, len(nums) - 1)
    return nums

print(rotate([1, 2, 3, 4, 5, 6, 7], 3))
```

```output
[5, 6, 7, 1, 2, 3, 4]
```

Time **O(n)**, space **O(1)**.

## 6. Majority element (Boyer-Moore voting)

**Problem.** Find the element that appears more than n/2 times.

**Idea.** Keep a candidate and a count; matching elements add one, different ones cancel. The majority survives.

```python
def majority(nums):
    candidate, count = None, 0
    for x in nums:
        if count == 0:
            candidate = x
        count += 1 if x == candidate else -1
    return candidate

print(majority([2, 2, 1, 1, 1, 2, 2]))
```

```output
2
```

Time **O(n)**, space **O(1)**.

:::tip
In an interview say the brute force first (for example "all pairs, O(n squared)"), then show how one idea (running minimum, two pointers, voting) removes the extra work.
:::
