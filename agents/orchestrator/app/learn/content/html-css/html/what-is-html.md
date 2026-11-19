---
title: What is HTML?
summary: HTML gives a web page its structure: headings, paragraphs, links and more, written as tags.
takeaways:
- HTML describes what things are on a page, not how they look
- Tags usually come in pairs: an opening and a closing tag
- Every page has a head (information) and a body (what people see)
---
## The skeleton of every web page

When you open a website, your browser reads a file written in **HTML** (HyperText Markup Language) and draws the page from it. HTML says *what each piece is*: a heading, a paragraph, a button. It does not say what colour or size. That is CSS, which comes later.

## Your first page

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8">
    <title>My first page</title>
  </head>
  <body>
    <h1>Hello, web!</h1>
    <p>This is my first page.</p>
  </body>
</html>
```

Save this as `index.html` and double-click it. It opens in your browser.

## Reading the code

| Part | What it does |
| --- | --- |
| `<!DOCTYPE html>` | tells the browser this is modern HTML |
| `<html>` | wraps the whole page |
| `<head>` | information about the page: its title, character set, styles |
| `<body>` | everything the visitor sees |
| `<h1>` | the main heading |
| `<p>` | a paragraph |

## Tags and elements

A **tag** is a word in angle brackets. Most tags come in pairs:

```html
<p>Some text</p>
```

`<p>` opens, `</p>` closes. The tags together with what is between them form an **element**.

Some elements have no content and need no closing tag, such as `<br>` (a line break) and `<img>` (an image).

## Attributes

Tags can carry extra information as attributes:

```html
<a href="https://www.skilldara.com">Visit SkillDARA</a>
```

`href` is the attribute, and the text in quotes is its value.

:::tip
Indent the code inside each element by two spaces. It makes mistakes such as a missing closing tag easy to see.
:::

:::note
Browsers are forgiving: a missing closing tag often still works, which can hide mistakes. Use a validator such as validator.w3.org when a page behaves oddly.
:::
