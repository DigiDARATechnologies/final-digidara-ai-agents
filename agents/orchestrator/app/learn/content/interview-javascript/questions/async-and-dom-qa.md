---
title: Async JavaScript and the DOM
summary: The DOM, event bubbling, promises, async and await, debouncing, storage and CORS.
kind: qa
takeaways:
- Explain promises with their three states
- Know bubbling and event delegation
- Be ready to compare localStorage, sessionStorage and cookies
---
### Q [Easy] What is the DOM?
The Document Object Model: the browser's tree of objects that represents the page. JavaScript reads and changes the page by working with it.

### Q [Medium] What are event bubbling and event delegation?
**Bubbling:** an event fires on the clicked element and then travels up to its parents. **Delegation:** instead of adding a listener to every child, add one on the parent and check `event.target` to see which child was clicked. It uses less memory and works for items added later.

### Q [Medium] What is a promise?
An object for a value that will arrive later. It is **pending**, then either **fulfilled** with a value or **rejected** with an error. You handle it with `.then()` and `.catch()`, or with `await`.

### Q [Medium] What is the difference between `async/await` and `.then()`?
They do the same job. `async/await` lets you write asynchronous code that reads top to bottom, with `try/catch` for errors. `.then()` chains callbacks. `await` only works inside an `async` function.

### Q [Hard] What does `Promise.all` do?
It takes several promises and returns one promise that resolves with an array of all the results **when all succeed**. If **any** one rejects, `Promise.all` rejects straight away. `Promise.allSettled` waits for all and reports each outcome.

### Q [Medium] What is debouncing?
Delaying a function until the user has stopped doing something for a short time, for example running a search only 300 ms after the last keystroke. It avoids sending a request on every key press.

```javascript
function debounce(fn, wait) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}
```

### Q [Medium] What is the difference between localStorage, sessionStorage and cookies?
`localStorage` keeps data until it is cleared. `sessionStorage` lasts only for the browser tab. Cookies are sent to the server with **every request** and can be set to expire. Cookies are for things the server needs, like a login session; storage is for the browser's own use.

### Q [Hard] What is CORS?
Cross-Origin Resource Sharing. By default a page may only call servers on its own origin. A server can send headers such as `Access-Control-Allow-Origin` to allow requests from another origin. It is enforced by the **browser**, so the fix is on the server.

:::interview
**Tip:** for any "what is X" question, give a one-line definition, then one example or one reason it matters. It keeps answers short and clear.
:::

:::practice mock-interview
Practise these answers out loud in a Mock Interview.
:::
