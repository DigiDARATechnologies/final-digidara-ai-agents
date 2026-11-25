---
title: Dynamic programming and backtracking problems
summary: Word break, decode ways, longest palindromic substring, coin change (ways) and N-Queens.
takeaways:
- Define dp[i] in words first
- Many string DP problems use dp over the prefix length
- Backtracking: choose, explore, undo, with pruning
---
## 1. Word break

**Problem.** Can the string be split into words from a dictionary?

**Idea.** `dp[i]` is True if the first `i` characters can be split. For each `i`, check every `j < i` where `dp[j]` is True and `s[j:i]` is a word.

```python
def word_break(s, words):
    words = set(words)
    dp = [True] + [False] * len(s)
    for i in range(1, len(s) + 1):
        for j in range(i):
            if dp[j] and s[j:i] in words:
                dp[i] = True
                break
    return dp[len(s)]

print(word_break("leetcode", ["leet", "code"]), word_break("catsandog", ["cats", "dog", "sand", "and", "cat"]))
```

```output
True False
```

## 2. Decode ways

**Problem.** `A=1, B=2, ... Z=26`. In how many ways can a digit string be decoded?

**Idea.** `dp[i]` = ways for the first `i` digits. Add `dp[i-1]` if the last digit is 1 to 9, and `dp[i-2]` if the last two digits are 10 to 26.

```python
def num_decodings(s):
    if not s or s[0] == "0":
        return 0
    dp = [1, 1]
    for i in range(2, len(s) + 1):
        ways = 0
        if s[i - 1] != "0":
            ways += dp[i - 1]
        if 10 <= int(s[i - 2:i]) <= 26:
            ways += dp[i - 2]
        dp.append(ways)
    return dp[-1]

print(num_decodings("12"), num_decodings("226"), num_decodings("06"))
```

```output
2 3 0
```

"226" can be 2-2-6, 22-6 or 2-26: three ways.

## 3. Longest palindromic substring

**Idea.** Expand around every possible centre (a letter or a gap between two letters).

```python
def longest_palindrome(s):
    best = ""
    for centre in range(len(s)):
        for left, right in ((centre, centre), (centre, centre + 1)):
            while left >= 0 and right < len(s) and s[left] == s[right]:
                left -= 1
                right += 1
            if right - left - 1 > len(best):
                best = s[left + 1:right]
    return best

print(longest_palindrome("babad"), longest_palindrome("cbbd"))
```

```output
bab bb
```

For "babad" both "bab" and "aba" are correct; either is accepted. Time **O(n squared)**.

## 4. Coin change: number of ways

**Idea.** Process coins one at a time; `ways[a]` counts the combinations that make amount `a`.

```python
def coin_change_ways(amount, coins):
    ways = [1] + [0] * amount
    for coin in coins:
        for a in range(coin, amount + 1):
            ways[a] += ways[a - coin]
    return ways[amount]

print(coin_change_ways(5, [1, 2, 5]))
```

```output
4
```

The four ways to make 5 are 5, 2+2+1, 2+1+1+1 and 1+1+1+1+1. Looping over **coins first** counts combinations, not orderings.

## 5. N-Queens (count solutions)

**Idea.** Place one queen per row; track the used columns and diagonals; backtrack when no column works.

```python
def n_queens(n):
    columns, diag1, diag2 = set(), set(), set()
    def place(row):
        if row == n:
            return 1
        count = 0
        for col in range(n):
            if col in columns or (row - col) in diag1 or (row + col) in diag2:
                continue
            columns.add(col); diag1.add(row - col); diag2.add(row + col)
            count += place(row + 1)
            columns.remove(col); diag1.remove(row - col); diag2.remove(row + col)
        return count
    return place(0)

print([n_queens(n) for n in (4, 5, 6, 8)])
```

```output
[2, 10, 4, 92]
```

## 6. Maximum product subarray

Track both the maximum and the minimum product ending at each position, because a negative number can turn the smallest product into the largest.

```python
def max_product(nums):
    best = high = low = nums[0]
    for x in nums[1:]:
        candidates = (x, high * x, low * x)
        high, low = max(candidates), min(candidates)
        best = max(best, high)
    return best

print(max_product([2, 3, -2, 4]), max_product([-2, 0, -1]))
```

```output
6 0
```
