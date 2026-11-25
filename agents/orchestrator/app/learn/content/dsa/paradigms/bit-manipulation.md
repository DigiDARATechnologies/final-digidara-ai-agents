---
title: Bit manipulation
summary: Use binary operations for fast tricks: odd or even, powers of two, counting bits, XOR to find a single number.
takeaways:
- Numbers are stored as bits; & | ^ ~ << >> work on them
- XOR cancels equal numbers: a ^ a = 0
- n & (n - 1) removes the lowest set bit
---
## Bits in Python

`13` in binary is `1101`. Python's operators work on those bits.

| Operator | Meaning | Example |
| --- | --- | --- |
| `a & b` | AND: 1 only if both are 1 | `12 & 10 = 8` |
| `a` OR-bar `b` (the vertical bar key) | OR: 1 if either is 1 | `12 OR 10 = 14` |
| `a ^ b` | XOR: 1 if they differ | `12 ^ 10 = 6` |
| `~a` | flip all bits | `~5 = -6` |
| `a << k` | shift left (multiply by 2 to the k) | `3 << 2 = 12` |
| `a >> k` | shift right (divide by 2 to the k) | `12 >> 2 = 3` |

```python
print(bin(13), 12 & 10, 12 | 10, 12 ^ 10, 3 << 2, 12 >> 2)
```

```output
0b1101 8 14 6 12 3
```

## Handy tricks

```python
n = 12
print("odd" if n & 1 else "even")            # last bit decides
print(n & (n - 1) == 0, 16 & 15 == 0)         # power of two test
print(bin(n).count("1"))                      # count set bits
print((n >> 2) & 1)                           # check bit number 2
print(n | (1 << 0), n & ~(1 << 2))            # set bit 0, clear bit 2
```

```output
even
False True
2
1
13 8
```

- `n & (n - 1)` clears the **lowest set bit**. For a power of two (only one bit set) the result is 0.
- `1 << k` makes a number with only bit `k` set (a **mask**).

## XOR: the cancelling operator

`a ^ a = 0` and `a ^ 0 = a`, and XOR does not care about order. So XOR-ing all numbers cancels pairs and leaves the single one.

**Single number**: every number appears twice except one.

```python
def single_number(nums):
    result = 0
    for x in nums:
        result ^= x
    return result

print(single_number([4, 1, 2, 1, 2]))
```

```output
4
```

O(n) time, **O(1) space**, no dictionary needed.

## Swap without a temporary

```python
a, b = 5, 9
a ^= b
b ^= a
a ^= b
print(a, b)
```

```output
9 5
```

(In Python `a, b = b, a` is simpler; the XOR swap is only an interview curiosity.)

## Counting bits for 0 to n

```python
def count_bits(n):
    dp = [0] * (n + 1)
    for i in range(1, n + 1):
        dp[i] = dp[i >> 1] + (i & 1)
    return dp

print(count_bits(8))
```

```output
[0, 1, 1, 2, 1, 2, 2, 3, 1]
```

## Subsets with bits

For n items there are `2 ** n` subsets, and each number from `0` to `2**n - 1` can be read as a **choice of items** (a bit set means "include").

```python
items = ["a", "b", "c"]
for mask in range(1 << len(items)):
    print([items[i] for i in range(len(items)) if mask >> i & 1])
```

```output
[]
['a']
['b']
['a', 'b']
['c']
['a', 'c']
['b', 'c']
['a', 'b', 'c']
```

:::note
Bit tricks appear in interviews as "do it without extra space" or "find the missing / single number". Learn XOR and `n & (n - 1)` well.
:::
