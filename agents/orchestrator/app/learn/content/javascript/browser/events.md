---
title: Events
summary: React to clicks, typing and form submits with event listeners.
takeaways:
- addEventListener runs a function when something happens
- The event object says what happened
- preventDefault stops the browser's built-in action
---
## Doing something when the user does something

```html
<button id="btn">Click me</button>
<p id="out"></p>
```

```javascript
const btn = document.querySelector("#btn");
const out = document.querySelector("#out");

btn.addEventListener("click", () => {
  out.textContent = "Clicked!";
});
```

`addEventListener(type, function)` runs the function every time that event happens on the element.

## Common events

| Event | When it fires |
| --- | --- |
| `click` | the element is clicked |
| `input` | the value of an input changes, on every keystroke |
| `change` | a select or checkbox changes |
| `submit` | a form is submitted |
| `keydown` | a key is pressed |
| `mouseover` | the mouse enters the element |

## The event object

The function receives an object describing the event:

```javascript
const input = document.querySelector("#name");

input.addEventListener("input", (event) => {
  out.textContent = `Hello, ${event.target.value}`;
});
```

`event.target` is the element the event happened on.

## Forms and preventDefault

A form submit reloads the page by default. Stop that to handle it yourself:

```javascript
const form = document.querySelector("form");

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const name = form.elements.name.value;
  console.log("Submitted", name);
});
```

## A small to-do example

```javascript
const list = document.querySelector("#list");
const text = document.querySelector("#task");

document.querySelector("#add").addEventListener("click", () => {
  if (!text.value.trim()) return;
  const li = document.createElement("li");
  li.textContent = text.value;
  list.appendChild(li);
  text.value = "";
});
```

:::tip
Many elements can share one listener on their parent (event delegation). Check `event.target` to see which child was clicked.
:::

:::interview
**Interviewers often ask:** "What is event bubbling?" An event fires on the clicked element and then travels up through its parents, so a parent can handle events from its children.
:::
