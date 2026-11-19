---
title: What is JavaScript?
summary: The language that makes web pages interactive, and how to run your first line.
takeaways:
- HTML is structure, CSS is style, JavaScript is behaviour
- It runs in every browser, and also on servers with Node.js
- console.log() is your first debugging tool
---
## The third part of a web page

A page has three layers:

| Layer | Job | Example |
| --- | --- | --- |
| HTML | structure | a button exists |
| CSS | style | the button is blue and rounded |
| JavaScript | behaviour | clicking the button shows a message |

JavaScript runs inside the browser, so the page can react without reloading. It also runs on servers through **Node.js**, which is why one language can build both sides of an app.

:::note
JavaScript and Java are different languages. The names are only a marketing accident from the 1990s.
:::

## Running JavaScript

Open any web page, press **F12**, and choose the **Console** tab. Type:

```javascript
console.log("Hello from JavaScript");
```

```output
Hello from JavaScript
```

To use it in a page, add a script just before the end of `<body>`:

```html
<script src="app.js"></script>
```

and write your code in `app.js`.

## Your first interaction

```html
<button id="hi">Say hi</button>
<script>
  document.getElementById("hi").addEventListener("click", function () {
    alert("Hi!");
  });
</script>
```

Clicking the button now shows a popup. You will learn each piece of this in the next lessons.

## console.log is your friend

`console.log(value)` prints a value in the console. Use it whenever you are not sure what a variable holds.

```javascript
let price = 120;
console.log("Price is", price);
```

:::tip
Statements end with a semicolon (`;`). JavaScript can often guess them, but writing them avoids surprises.
:::
