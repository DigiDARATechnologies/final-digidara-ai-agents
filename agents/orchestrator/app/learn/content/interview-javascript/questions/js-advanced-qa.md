---
title: Advanced JavaScript concepts
summary: Closures, hoisting, this, prototypes, the event loop, promises, async/await and modern syntax.
kind: qa
takeaways:
- Explain closures and the event loop with a short example
- Know var, let, const, hoisting and the temporal dead zone
- Understand this, prototypes and promises
---
### Q [Medium] What is a closure?
A function that **remembers the variables of the scope where it was created**, even after that outer function has finished.

```javascript
function counter() {
  let count = 0;
  return () => ++count;
}
const next = counter();
next();   // 1
next();   // 2
```

Uses: private data, factories, callbacks, memoization.

### Q [Easy] `var` vs `let` vs `const`?
`var` is function scoped and hoisted (initialised as `undefined`). `let` and `const` are **block scoped**. `const` cannot be reassigned (but an object it holds can still change). Prefer `const`, then `let`.

### Q [Medium] What is hoisting and the temporal dead zone?
Declarations are moved to the top of their scope. `var` is available (as `undefined`) before its line. `let` and `const` are hoisted too, but reading them before the declaration throws a `ReferenceError`: that gap is the **temporal dead zone**.

### Q [Medium] How does `this` work?
`this` depends on **how a function is called**: in a method call it is the object; in a plain function it is `undefined` (strict mode) or the global object; with `call`, `apply` or `bind` you set it; **arrow functions** do not have their own `this` and use the surrounding one.

### Q [Medium] `call`, `apply` and `bind`?
All set `this`. `call(obj, a, b)` calls immediately with arguments listed. `apply(obj, [a, b])` calls immediately with an array. `bind(obj)` returns a **new function** with `this` fixed.

### Q [Medium] What is the prototype chain?
Every object has a hidden link to a prototype object. If a property is not found on the object, JavaScript looks up the chain. Classes are a cleaner syntax over this.

### Q [Medium] What is the event loop?
JavaScript runs one task at a time on a single thread. Async work (timers, network) is handled by the browser or Node, and its callbacks wait in queues. When the **call stack is empty**, the loop first runs all **microtasks** (promise callbacks), then the next **macrotask** (such as `setTimeout`).

### Q [Medium] What is a promise? What are its states?
An object representing a value that will be available later. States: **pending**, **fulfilled** (resolved) and **rejected**. Use `.then`, `.catch`, `.finally`.

### Q [Medium] `async`/`await`?
Syntax over promises that lets you write async code like normal code. `await` pauses the function until the promise settles; use `try/catch` for errors. `await Promise.all([a(), b()])` runs tasks in parallel.

### Q [Medium] `==` vs `===`?
`==` converts types before comparing (`"5" == 5` is true). `===` compares without conversion (`"5" === 5` is false). Prefer `===`.

### Q [Medium] What is destructuring and the spread operator?
Destructuring unpacks values: `const { name, age } = user;` or `const [a, b] = list;`. Spread copies or merges: `const copy = { ...user, age: 21 };` and `[...a, ...b]`.

### Q [Medium] `map`, `filter` and `reduce`?
`map` transforms each item into a new array, `filter` keeps items that pass a test, `reduce` combines all items into one value.

```javascript
const total = [1, 2, 3, 4].filter(n => n % 2 === 0).map(n => n * 10).reduce((a, b) => a + b, 0);
```

### Q [Medium] What is debouncing and throttling?
**Debounce** waits until the user stops (search box typing) before running a function. **Throttle** runs it at most once per time interval (scroll handlers).

### Q [Hard] Shallow vs deep copy of an object?
Spread and `Object.assign` make shallow copies (nested objects are shared). Use `structuredClone(obj)` for a deep copy.

### Q [Medium] What is event delegation?
Attaching one listener to a parent and using `event.target` to handle clicks from many children. It saves memory and works for elements added later.
