---
title: Conditions and loops
summary: Decide with if and else, and repeat with for, while and for...of.
takeaways:
- if / else if / else chooses a path
- for loops count; for...of walks an array
- && , || and ! combine conditions
---
## if, else if, else

```javascript
const marks = 72;

if (marks >= 90) {
  console.log("Distinction");
} else if (marks >= 60) {
  console.log("First class");
} else {
  console.log("Keep practising");
}
```

```output
First class
```

Blocks sit between `{ }`. Indentation is for readability only.

## Combining tests

```javascript
const age = 20;
const hasId = true;

if (age >= 18 && hasId) {
  console.log("Allowed");
}
if (age < 13 || age > 65) {
  console.log("Discount");
}
```

`&&` is and, `||` is or, `!` is not.

## The for loop

```javascript
for (let i = 1; i <= 3; i++) {
  console.log(i);
}
```

The three parts are: start (`let i = 1`), keep going while (`i <= 3`), step (`i++`, meaning add one).

## for...of

The clearest way to walk an array:

```javascript
const fruits = ["apple", "mango", "banana"];
for (const fruit of fruits) {
  console.log(fruit);
}
```

## while

```javascript
let count = 3;
while (count > 0) {
  console.log(count);
  count--;
}
```

:::warning
Remember to change the condition inside a `while` loop, or it never ends and the page freezes.
:::

## switch

```javascript
const day = "Mon";
switch (day) {
  case "Mon":
    console.log("Start of the week");
    break;
  default:
    console.log("Another day");
}
```

:::tip
`break` leaves a loop early and `continue` skips to the next round, just as in other languages.
:::
