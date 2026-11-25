---
title: Project 3: Password generator and strength checker
summary: Build tools to generate secure passwords and check how strong a password is, learning strings, the secrets module, and how to turn rules into code.
takeaways:
- Use the secrets module, not random, for anything security-related
- Length matters more than complicated symbols
- Turn rules into small functions that return clear results and feedback
---
## Why this project

Weak passwords are one of the biggest causes of hacked accounts. This project teaches **strings, loops, conditions and the standard library**, and the topic is useful to know.

## Step 1: the generator

Computers have two kinds of random numbers. The `random` module is fine for games but **predictable**. For passwords and tokens use the `secrets` module, which is designed for security.

```python
import secrets
import string

def generate_password(length=14, use_symbols=True):
    if length < 8:
        raise ValueError("Use at least 8 characters")
    alphabet = string.ascii_letters + string.digits
    if use_symbols:
        alphabet += "!@#$%^&*-_?"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_symbol = (not use_symbols) or any(c in "!@#$%^&*-_?" for c in password)
        if has_lower and has_upper and has_digit and has_symbol:
            return password              # only accept a password with every kind of character

password = generate_password()
print("length:", len(password))
print("has lowercase, uppercase, digit and symbol:",
      any(c.islower() for c in password), any(c.isupper() for c in password),
      any(c.isdigit() for c in password), any(c in "!@#$%^&*-_?" for c in password))
print("two passwords are different:", generate_password() != generate_password())
```

```output
length: 14
has lowercase, uppercase, digit and symbol: True True True True
two passwords are different: True
```

We print properties of the password, not the password itself, because each run gives a different one. The loop keeps generating until the password contains every character type.

## Step 2: how big is the search space?

Why does length matter so much? Count the possible passwords an attacker would have to try:

```python
import math

def possible_passwords(length, alphabet_size):
    return alphabet_size ** length

for label, size in (("digits only", 10), ("lowercase letters", 26), ("letters and digits", 62), ("letters, digits and symbols", 73)):
    for length in (8, 12):
        combos = possible_passwords(length, size)
        print(f"{label:<28} length {length:>2}: about 10^{math.log10(combos):.1f} combinations")
```

```output
digits only                  length  8: about 10^8.0 combinations
digits only                  length 12: about 10^12.0 combinations
lowercase letters            length  8: about 10^11.3 combinations
lowercase letters            length 12: about 10^17.0 combinations
letters and digits           length  8: about 10^14.3 combinations
letters and digits           length 12: about 10^21.5 combinations
letters, digits and symbols  length  8: about 10^14.9 combinations
letters, digits and symbols  length 12: about 10^22.4 combinations
```

Each extra character multiplies the search space. Even using only lowercase letters, a 12-character password has about **half a million times** more possibilities than an 8-character one (10^17.0 against 10^11.3). That is why modern advice says: **make it long**.

## Step 3: the strength checker

Turn the rules into code. We return a score and helpful messages.

```python
import string

COMMON = {"password", "123456", "12345678", "qwerty", "abc123", "welcome", "iloveyou", "admin", "letmein", "india123"}

def check_strength(password):
    score = 0
    tips = []

    if len(password) >= 12:
        score += 2
    elif len(password) >= 8:
        score += 1
    else:
        tips.append("Use at least 8 characters (12 or more is better)")

    if any(c.islower() for c in password) and any(c.isupper() for c in password):
        score += 1
    else:
        tips.append("Mix uppercase and lowercase letters")

    if any(c.isdigit() for c in password):
        score += 1
    else:
        tips.append("Add a number")

    if any(c in string.punctuation for c in password):
        score += 1
    else:
        tips.append("Add a symbol such as ! or #")

    if password.lower() in COMMON:
        score = 0
        tips.append("This is a very common password: never use it")

    labels = {0: "very weak", 1: "very weak", 2: "weak", 3: "fair", 4: "good", 5: "strong"}
    return score, labels[min(score, 5)], tips

for pw in ("password", "Ravi2005", "Tr1cky#Password", "correct horse battery staple"):
    score, label, tips = check_strength(pw)
    print(f"{pw!r:<32} score {score}  {label}")
    for tip in tips:
        print("     -", tip)
```

```output
'password'                       score 0  very weak
     - Mix uppercase and lowercase letters
     - Add a number
     - Add a symbol such as ! or #
     - This is a very common password: never use it
'Ravi2005'                       score 3  fair
     - Add a symbol such as ! or #
'Tr1cky#Password'                score 5  strong
'correct horse battery staple'   score 2  weak
     - Mix uppercase and lowercase letters
     - Add a number
     - Add a symbol such as ! or #
```

Look closely at the last one. The four-word phrase is actually **very hard to guess** (28 characters, made of unrelated words), but our simple checker rates it only "weak" because it has no capital letter, digit or symbol. That is a limitation of simple rules: they measure the *kinds* of characters, not how guessable the password really is. Professional tools use large lists of leaked passwords and measure real "guessability" (for example the `zxcvbn` library). `Ravi2005`, on the other hand, scores "fair" even though it is a name plus a year, the first pattern an attacker tries. Step 4 adds a check for exactly that.

## Step 4: add a check against reused patterns

Attackers try patterns like a name plus a year first. We can add a simple warning:

```python
import re

def looks_predictable(password):
    problems = []
    if re.search(r"(19|20)\d\d$", password):
        problems.append("ends with a year")
    if re.search(r"(.)\1\1", password):
        problems.append("repeats a character three times")
    if re.search(r"(0123|1234|2345|abcd|qwer)", password.lower()):
        problems.append("contains a simple sequence")
    return problems

for pw in ("Ravi2005", "aaa!Mnop9", "Qwerty!x7R", "m4Rk-t#Vq9zL"):
    print(f"{pw:<16} {looks_predictable(pw) or 'no obvious patterns'}")
```

```output
Ravi2005         ['ends with a year']
aaa!Mnop9        ['repeats a character three times']
Qwerty!x7R       ['contains a simple sequence']
m4Rk-t#Vq9zL     no obvious patterns
```

## Step 5: a simple command-line tool

```py
import getpass

def main():
    print("1) Generate a password   2) Check a password")
    choice = input("Choose: ").strip()
    if choice == "1":
        length = int(input("Length (12 or more recommended): "))
        print("Your password:", generate_password(length))
    elif choice == "2":
        password = getpass.getpass("Password to check (hidden): ")      # getpass hides what you type
        score, label, tips = check_strength(password)
        print(f"Strength: {label} ({score}/5)")
        for tip in tips + looks_predictable(password):
            print(" -", tip)

if __name__ == "__main__":
    main()
```

`getpass.getpass` hides typing, as real login forms do.

## What real systems do differently

| Topic | Practice |
| --- | --- |
| **Storing passwords** | never store them as text: store a salted, slow **hash** (bcrypt, argon2); see the Flask authentication lesson |
| **Checking strength** | compare against lists of leaked passwords (Have I Been Pwned) |
| **Protecting accounts** | two-factor authentication matters more than complicated rules |
| **Remembering passwords** | a password manager creates and stores a different long password per site |

:::warning
Never type a real password into a program you are testing, never print it to a log, and never put real passwords in your code or on GitHub. Use fake examples when you demonstrate.
:::

## Improvements to try

| Idea | What you practise |
| --- | --- |
| a passphrase generator (several random words from a word list) | lists, files, `secrets.choice` |
| copy the password to the clipboard | libraries (`pyperclip`) |
| check the password against a file of common passwords | files, sets (fast lookups) |
| a small Tkinter or web interface | user interfaces |
| estimate crack time from the search space | maths, formatting |
