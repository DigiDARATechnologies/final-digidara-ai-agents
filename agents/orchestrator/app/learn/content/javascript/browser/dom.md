---
title: The DOM: changing the page
summary: Find elements, change their text and style, and add or remove elements.
takeaways:
- The DOM is the page as objects JavaScript can change
- querySelector finds an element using a CSS selector
- Change text with textContent, classes with classList
---
## The page as objects

When the browser loads HTML, it builds a tree of objects called the **DOM** (Document Object Model). JavaScript changes the page by changing those objects.

```html
<h1 id="title">Welcome</h1>
<p class="note">Hello</p>
<ul id="list"></ul>
```

## Finding elements

```javascript
const title = document.querySelector("#title");
const note = document.querySelector(".note");
const allNotes = document.querySelectorAll(".note");
```

`querySelector` takes a CSS selector and returns the first match. `querySelectorAll` returns all of them.

## Changing them

```javascript
title.textContent = "Welcome back!";
title.style.color = "blue";
note.classList.add("highlight");
note.classList.remove("highlight");
note.classList.toggle("highlight");
```

| Property or method | What it does |
| --- | --- |
| `textContent` | gets or sets the plain text |
| `style.property` | sets an inline style |
| `classList.add / remove / toggle` | changes CSS classes |
| `setAttribute("src", "a.png")` | sets an attribute |

Prefer changing **classes** over inline styles: your CSS stays in the stylesheet.

## Adding and removing elements

```javascript
const list = document.querySelector("#list");

const item = document.createElement("li");
item.textContent = "Learn the DOM";
list.appendChild(item);

item.remove();
```

## Building a list from data

```javascript
const skills = ["HTML", "CSS", "JavaScript"];
for (const skill of skills) {
  const li = document.createElement("li");
  li.textContent = skill;
  list.appendChild(li);
}
```

:::warning
Do not put text from users into `innerHTML`. Someone can type `<script>` or other markup and attack your visitors. Use `textContent`, which treats it as plain text.
:::
