---
title: Project 1: Number guessing game
summary: Build a game in Python while learning to separate game logic from input, write testable functions, and find the best strategy with a little maths.
takeaways:
- Put the rules in small functions, and keep input and printing separate, so you can test the rules
- A while or for loop with a clear stopping condition drives the game
- Binary search wins in at most 7 guesses from 1 to 100
---
## The idea

The computer picks a secret number from 1 to 100. The player guesses, and the computer says "too low", "too high" or "correct". The player has 7 tries.

**Version 1 (MVP):** one game, 7 tries, hints.
**Later:** difficulty levels, scores, play again, a hint system.

## Step 1: the rule

The heart of the game is one small function that compares a guess with the secret.

```python
def check_guess(secret, guess):
    if guess < secret:
        return "too low"
    if guess > secret:
        return "too high"
    return "correct"

print(check_guess(40, 25))
print(check_guess(40, 60))
print(check_guess(40, 40))
```

```output
too low
too high
correct
```

Test each small piece as you write it. This function does **no input and no printing of its own**, which is what makes it easy to test.

## Step 2: the game loop, testable

A game that asks the player for input is hard to test, because a person has to type. So we write the loop to take a **list of guesses**, and the interactive version will feed it real input later.

```python
def play(secret, guesses, max_tries=7):
    for attempt, guess in enumerate(guesses, start=1):
        result = check_guess(secret, guess)
        print(f"Attempt {attempt}: {guess} is {result}")
        if result == "correct":
            return attempt                     # the player won, in this many tries
        if attempt == max_tries:
            break
    return None                                # the player ran out of tries

won_in = play(secret=40, guesses=[50, 25, 37, 43, 40])
print("won in:", won_in)

print()
lost = play(secret=40, guesses=[1, 2, 3], max_tries=3)
print("result when out of tries:", lost)
```

```output
Attempt 1: 50 is too high
Attempt 2: 25 is too low
Attempt 3: 37 is too low
Attempt 4: 43 is too high
Attempt 5: 40 is correct
won in: 5

Attempt 1: 1 is too low
Attempt 2: 2 is too low
Attempt 3: 3 is too low
result when out of tries: None
```

The function **returns** the number of attempts when the player wins, and `None` when they do not. The caller decides what to print. That is cleaner than printing "You win" inside a function that other code may want to reuse.

## Step 3: the interactive version

Now connect real input. Save this as `game.py` and run it with `python game.py`:

```py
import random

def read_guess():
    while True:
        text = input("Your guess (1 to 100): ")
        if text.isdigit() and 1 <= int(text) <= 100:
            return int(text)
        print("Please type a whole number from 1 to 100.")     # handle bad input instead of crashing

def main():
    secret = random.randint(1, 100)
    print("I am thinking of a number from 1 to 100. You have 7 tries.")
    for attempt in range(1, 8):
        guess = read_guess()
        result = check_guess(secret, guess)
        if result == "correct":
            print(f"Correct! You won in {attempt} tries.")
            return
        print(f"That is {result}.")
    print(f"Out of tries. The number was {secret}.")

if __name__ == "__main__":
    main()
```

Three things to notice:

1. `read_guess` keeps asking until the input is valid. A beginner program crashes on `abc`; a good one does not.
2. `random.randint(1, 100)` includes both ends.
3. `if __name__ == "__main__":` runs `main()` only when you start this file directly, not when another file imports it (for tests).

## Step 4: find the best strategy

Is 7 tries fair? If you always guess the **middle** of the remaining range, each guess halves the possibilities (this is **binary search**). Let us prove that 7 tries is always enough for 1 to 100:

```python
def binary_search_guesses(secret, low=1, high=100):
    guesses = []
    while low <= high:
        middle = (low + high) // 2
        guesses.append(middle)
        result = check_guess(secret, middle)
        if result == "correct":
            return guesses
        if result == "too low":
            low = middle + 1
        else:
            high = middle - 1

print("secret 40 is found with guesses:", binary_search_guesses(40))

worst = max(len(binary_search_guesses(secret)) for secret in range(1, 101))
print("the most tries ever needed for 1 to 100:", worst)
print("secrets that need that many tries:", sum(len(binary_search_guesses(s)) == worst for s in range(1, 101)))
```

```output
secret 40 is found with guesses: [50, 25, 37, 43, 40]
the most tries ever needed for 1 to 100: 7
secrets that need that many tries: 37
```

With the middle-guess strategy, **no number from 1 to 100 needs more than 7 tries**, so 7 is a fair limit. This is the same idea computers use to search sorted lists, so this little game teaches a famous algorithm. For 1 to 1000 you would need at most 10 tries, because 2 to the power of 10 is 1,024.

## Step 5: let the computer play

Because `play` takes guesses as a list, we can run the game automatically to check it is correct:

```python
import random

random.seed(7)
results = []
for _ in range(1000):
    secret = random.randint(1, 100)
    guesses = binary_search_guesses(secret)
    results.append(len(guesses))

print("games played:", len(results))
print("longest game:", max(results), "tries")
print("average game:", round(sum(results) / len(results), 2), "tries")
```

```output
games played: 1000
longest game: 7 tries
average game: 5.78 tries
```

A thousand games finish in at most 7 tries, with an average of around 5.8. Testing with many cases at once is a powerful habit.

## Improvements to try

| Idea | What you practise |
| --- | --- |
| three levels: easy (1 to 20), medium (1 to 100), hard (1 to 1000) | variables and `max_tries` calculated from the range |
| count wins and losses across several rounds | variables, loops, "play again?" |
| a score: more points for fewer tries | arithmetic |
| a hint: "the number is even/odd" after two wrong guesses | conditions |
| save the best score to a file | file input and output |
| a graphical or web version later | a new interface for the same logic |

:::remember
The skill from this project: **keep rules separate from input and output.** That one habit makes code testable, reusable (the same logic can power a terminal game and a web page), and much easier to fix.
:::
