---
title: Fetching data and promises
summary: Get data from an API with fetch, async and await, and handle errors.
takeaways:
- fetch asks a server for data and returns a promise
- await waits for a promise inside an async function
- Always check the response and catch errors
---
## Waiting for the network

Getting data from a server takes time. JavaScript does not freeze while it waits; it uses **promises**: an object that stands for a value that will arrive later.

## fetch with async and await

```javascript
async function loadUser() {
  const response = await fetch("https://jsonplaceholder.typicode.com/users/1");
  const user = await response.json();
  console.log(user.name);
}

loadUser();
```

- `fetch(url)` starts the request and returns a promise.
- `await` pauses **that function** until the promise gives its result.
- `response.json()` reads the body as JSON, which is another promise.

`await` only works inside a function marked `async`.

## Handling errors

```javascript
async function loadUser() {
  try {
    const response = await fetch("https://jsonplaceholder.typicode.com/users/1");
    if (!response.ok) {
      throw new Error(`Server said ${response.status}`);
    }
    const user = await response.json();
    console.log(user.name);
  } catch (error) {
    console.log("Could not load:", error.message);
  }
}
```

:::warning
`fetch` only fails on network problems. A 404 or 500 still counts as a successful fetch, so always check `response.ok`.
:::

## Showing the data

```javascript
async function showUsers() {
  const response = await fetch("https://jsonplaceholder.typicode.com/users");
  const users = await response.json();
  const list = document.querySelector("#users");
  for (const user of users) {
    const li = document.createElement("li");
    li.textContent = user.name;
    list.appendChild(li);
  }
}
```

## Sending data

```javascript
await fetch("/api/notes", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ text: "Remember the milk" }),
});
```

## The same thing with .then

Before `await`, promises were chained:

```javascript
fetch(url)
  .then((response) => response.json())
  .then((data) => console.log(data))
  .catch((error) => console.log(error));
```

Both styles work; `async/await` reads more like normal code.

:::interview
**Interviewers often ask:** "What is a promise?" An object representing the eventual result of an asynchronous operation. It is pending, then either fulfilled with a value or rejected with an error.
:::
