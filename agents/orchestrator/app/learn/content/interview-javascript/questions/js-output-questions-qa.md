---
title: JavaScript output questions
summary: Predict the output: hoisting, coercion, closures in loops, the event loop, equality, this and array methods.
kind: qa
takeaways:
- Trace the code in the order the engine runs it
- Know the classic traps: var in loops, coercion and the event loop order
- Explain WHY, not only the result
---
Predict the output first. Each snippet was run in Node and the output below is real.

### Q [Medium] What does this print? (hoisting)
```javascript
console.log(a);
var a = 5;
console.log(a);
```

```output
undefined
5
```
`var a` is hoisted and starts as `undefined`; the assignment happens at its line.

### Q [Medium] What does this print? (temporal dead zone)
```javascript
try {
  console.log(b);
  let b = 5;
} catch (e) {
  console.log(e.name);
}
```

```output
ReferenceError
```
`let` variables cannot be read before their declaration.

### Q [Medium] What does this print? (type coercion)
```javascript
console.log(typeof null, [] + [], '2' + 1, '2' - 1, 0.1 + 0.2 === 0.3);
```

```output
object  21 1 false
```
`typeof null` is a famous historical quirk, and `[] + []` is an empty string (the blank in the output). `+` with a string joins; `-` converts to numbers. Floating point is inexact.

### Q [Medium] What does this print? (var in a loop with setTimeout)
```javascript
for (var i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 0);
}
```

```output
3
3
3
```
`var` is shared by all callbacks, which run after the loop ends (i is 3).

### Q [Medium] What does this print? (let in a loop)
```javascript
for (let i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 0);
}
```

```output
0
1
2
```
`let` creates a **new variable for each iteration**, so each callback keeps its own value.

### Q [Medium] What does this print? (event loop order)
```javascript
console.log('1');
setTimeout(() => console.log('2'), 0);
Promise.resolve().then(() => console.log('3'));
console.log('4');
```

```output
1
4
3
2
```
Synchronous code first (1, 4), then microtasks (promise callbacks, 3), then macrotasks (timers, 2).

### Q [Medium] What does this print? (equality)
```javascript
console.log(null == undefined, null === undefined, NaN === NaN, [1] == 1);
```

```output
true false false true
```
`null == undefined` is true but they are different types; `NaN` is not equal to anything, even itself.

### Q [Medium] What does this print? (this in arrow vs normal function)
```javascript
const user = {
  name: 'Asha',
  normal() { return this.name; },
  arrow: () => typeof this,
};
console.log(user.normal(), user.arrow());
```

```output
Asha object
```
A normal method gets `this` from the call (`user`). An arrow function uses the outer `this`, which is not `user` (at the top level of a Node module it is an empty object).

### Q [Medium] What does this print? (array methods)
```javascript
const nums = [1, 2, 3, 4, 5];
console.log(nums.filter(n => n % 2).map(n => n * n), nums.reduce((a, b) => a + b, 0), nums.slice(1, 3), nums.indexOf(9));
```

```output
[ 1, 9, 25 ] 15 [ 2, 3 ] -1
```
`filter(n => n % 2)` keeps odd numbers; `slice(1, 3)` excludes the end index; `indexOf` returns -1 when not found.
