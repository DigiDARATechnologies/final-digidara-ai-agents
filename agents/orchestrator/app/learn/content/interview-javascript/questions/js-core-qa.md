---
title: JavaScript core
summary: var, let and const, equality, hoisting, closures, this, and array methods.
kind: qa
takeaways:
- Know var, let and const and the scope of each
- Explain closures and this in a sentence and an example
- Know the difference between map, filter and forEach
---
### Q [Easy] What is the difference between `var`, `let` and `const`?
`var` is function-scoped and can be redeclared, which causes bugs. `let` and `const` are **block-scoped**. `const` cannot be reassigned (but an object it holds can still change). Prefer `const`, then `let`, and avoid `var`.

### Q [Easy] What is the difference between `==` and `===`?
`==` converts types before comparing (`5 == "5"` is true). `===` compares value **and** type (`5 === "5"` is false). Use `===`.

### Q [Medium] What is hoisting?
JavaScript moves declarations to the top of their scope before running. Function declarations are fully hoisted. `var` is hoisted and set to `undefined`. `let` and `const` are hoisted but **cannot be used before their line** (the temporal dead zone).

### Q [Medium] What is a closure?
A function that remembers the variables from the place where it was created, even after the outer function has finished.

```javascript
function counter() {
  let n = 0;
  return () => ++n;
}
const next = counter();
next();   // 1
next();   // 2
```

### Q [Medium] How does `this` work?
`this` depends on **how a function is called**. In a method call (`obj.fn()`) it is `obj`. In a plain function call it is `undefined` in strict mode. Arrow functions do not have their own `this`; they use the one from where they were written.

### Q [Medium] What is the difference between `null` and `undefined`?
`undefined` means a variable has been declared but has no value yet. `null` is a value you set on purpose to mean "nothing".

### Q [Medium] What are the differences between `map`, `filter` and `forEach`?
`map` returns a **new array** with each item transformed. `filter` returns a new array with only items that pass a test. `forEach` just runs a function for each item and returns nothing.

### Q [Medium] What is the difference between an arrow function and a normal function?
Arrow functions have a shorter syntax, no own `this`, no `arguments` object and cannot be used as constructors. Use them for short callbacks.

### Q [Hard] What is the event loop?
JavaScript runs one thing at a time on a single thread. Slow work (timers, network) is handed to the browser. When it finishes, its callback waits in a queue, and the **event loop** runs it once the current code has finished. Promise callbacks (microtasks) run before timer callbacks.

:::practice mock-interview
Practise explaining closures and the event loop in a Mock Interview.
:::
