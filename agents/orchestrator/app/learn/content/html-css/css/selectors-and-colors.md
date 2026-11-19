---
title: Selectors, colours and text
summary: Pick elements with tag, class and id selectors, then set colours, fonts and text.
takeaways:
- Tag, class (.) and id (#) selectors pick elements
- Colours can be names, hex codes or rgb values
- Combine selectors to target precisely
---
## Choosing what to style

```html
<h1 id="title">Welcome</h1>
<p class="note">Read this first.</p>
<p>A normal paragraph.</p>
```

```css
p { margin: 8px 0; }        /* every paragraph */
.note { color: #b45309; }   /* every element with class="note" */
#title { text-align: center; }  /* the one element with id="title" */
```

| Selector | Picks |
| --- | --- |
| `p` | all `<p>` elements |
| `.note` | elements with `class="note"` |
| `#title` | the element with `id="title"` |
| `nav a` | links **inside** a nav |
| `h1, h2` | both h1 and h2 |
| `a:hover` | a link while the mouse is over it |

An `id` must be unique on a page. A class can be used many times, so prefer classes.

## Colours

```css
color: red;                 /* a name */
color: #1e40af;             /* hex code */
color: rgb(30, 64, 175);    /* red, green, blue (0 to 255) */
background-color: #f1f5f9;
```

## Text

```css
body {
  font-family: Arial, sans-serif;
  font-size: 16px;
  line-height: 1.6;       /* space between lines */
}

h1 {
  font-weight: 700;
  text-align: center;
  text-transform: uppercase;
}

a {
  text-decoration: none;
}
```

## Hover and focus

```css
button {
  background: #1e40af;
  color: white;
}
button:hover {
  background: #1d4ed8;
}
```

:::remember
Always check that text has enough contrast with its background. Light grey on white is hard to read for many people.
:::

:::tip
Use a **class** for almost everything. Ids are for one-off hooks (like linking to a section), and tag selectors are for base styles such as `body` and `a`.
:::
