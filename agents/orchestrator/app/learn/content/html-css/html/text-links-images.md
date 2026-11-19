---
title: Text, links and images
summary: Headings, paragraphs, emphasis, links and images, with accessible alt text.
takeaways:
- Use h1 to h6 for headings in order, with one h1 per page
- The a tag links pages; the img tag shows pictures
- Always give an image an alt description
---
## Headings and paragraphs

```html
<h1>Main title</h1>
<h2>Section</h2>
<h3>Sub-section</h3>
<p>A paragraph of text.</p>
```

Use headings for **structure**, not size. Screen readers and Google use them to understand your page. Use one `<h1>`, then `<h2>` for sections, and so on in order.

## Emphasis

```html
<p>This is <strong>important</strong> and this is <em>stressed</em>.</p>
```

`<strong>` is bold (important) and `<em>` is italic (emphasis). Use them for meaning, not just looks.

## Links

```html
<a href="about.html">About us</a>
<a href="https://example.com" target="_blank" rel="noopener">Open in a new tab</a>
```

- `href` is where the link goes.
- A path like `about.html` points to a file on the same site.
- `target="_blank"` opens a new tab; add `rel="noopener"` for safety.

## Images

```html
<img src="photo.jpg" alt="A student coding on a laptop" width="400">
```

| Attribute | Purpose |
| --- | --- |
| `src` | the image file |
| `alt` | a text description, read aloud for people who cannot see the image and shown if it fails to load |
| `width`, `height` | reserve space so the page does not jump while loading |

:::warning
Never leave out `alt`. It is required for accessibility, and it helps search engines understand your picture.
:::

## Line breaks and dividers

```html
<p>Line one<br>Line two</p>
<hr>
```

## Comments

```html
<!-- This note is not shown on the page -->
```

:::interview
**Interviewers often ask:** "What is the difference between `<strong>` and `<b>`?" Both look bold. `<strong>` says the text is important, which assistive technology reads with emphasis. `<b>` is only visual.
:::
