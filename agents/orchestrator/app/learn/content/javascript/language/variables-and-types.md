---
title: Variables and types
summary: Declare values with let and const, and meet strings, numbers, booleans, null and undefined.
takeaways:
- Use const by default and let when the value changes
- The basic types are string, number, boolean, null and undefined
- Use === to compare, not ==
---
## let and const

```javascript
let score = 10;      // can change
score = 15;

const name = "Asha"; // cannot be reassigned
```

Use `const` unless you know the value will change. Avoid the old `var`; its scoping rules cause bugs.

## Types

```javascript
let city = "Chennai";     // string
let age = 21;             // number (whole or decimal)
let ok = true;            // boolean
let nothing = null;       // empty on purpose
let notSet;               // undefined: declared, no value yet

console.log(typeof city, typeof age, typeof ok);
```

```output
string number boolean
```

## Template strings

Backticks let you put values inside text:

```javascript
const name = "Asha";
console.log(`Hello, ${name}! Next year you are ${21 + 1}.`);
```

```output
Hello, Asha! Next year you are 22.
```

## Comparing: === not ==

```javascript
console.log(5 === "5");   // false: different types
console.log(5 == "5");    // true: JavaScript converts, which surprises people
```

`===` checks value **and** type. Use it nearly always.

## Truthy and falsy

These count as false in a condition: `false`, `0`, `""`, `null`, `undefined`, `NaN`. Everything else is true.

```javascript
const name = "";
if (!name) {
  console.log("Please enter a name");
}
```

:::warning
`0.1 + 0.2` is `0.30000000000000004` in JavaScript, just as in Python. Round money with `toFixed(2)`.
:::

:::interview
**Interviewers often ask:** "What is the difference between `null` and `undefined`?" `undefined` means a variable has no value yet. `null` is a value you set to say "nothing here".
:::
