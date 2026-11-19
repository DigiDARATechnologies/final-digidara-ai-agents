---
title: Functions
summary: Reuse code with function declarations and arrow functions; understand parameters, return and scope.
takeaways:
- A function packages steps under a name
- Arrow functions are a short form: (a, b) => a + b
- Variables declared inside a function stay inside it
---
## Declaring a function

```javascript
function greet(name) {
  return `Hello, ${name}!`;
}

console.log(greet("Asha"));
```

```output
Hello, Asha!
```

`name` is a **parameter**, and `return` sends a value back to where the function was called.

## Arrow functions

A shorter way to write one:

```javascript
const add = (a, b) => a + b;
console.log(add(2, 3));   // 5
```

With one expression the `return` is implicit. With several lines use braces and `return`:

```javascript
const grade = (marks) => {
  if (marks >= 40) return "Pass";
  return "Fail";
};
```

## Default values

```javascript
function area(width, height = 1) {
  return width * height;
}
console.log(area(4));     // 4
```

## Functions are values

You can store a function in a variable and pass it to another function. This is used constantly:

```javascript
const numbers = [1, 2, 3];
const doubled = numbers.map((n) => n * 2);
console.log(doubled);   // [2, 4, 6]
```

## Scope

```javascript
function demo() {
  const secret = 42;
}
demo();
console.log(secret);   // ReferenceError: secret is not defined
```

A variable made inside a function exists only there.

## Closures in one sentence

A function remembers the variables around it when it was created:

```javascript
function counter() {
  let n = 0;
  return () => ++n;
}
const next = counter();
console.log(next(), next());   // 1 2
```

:::interview
**Interviewers often ask:** "What is a closure?" A function together with the variables from the place it was created in, which it can still use after that outer function has finished.
:::

:::practice mock-interview
Practise explaining closures out loud in a Mock Interview.
:::
