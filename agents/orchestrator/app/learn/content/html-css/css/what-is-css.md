---
title: What is CSS?
summary: CSS styles HTML: how to add it, how a rule is written and how the cascade decides.
takeaways:
- CSS controls how HTML looks: colour, size, spacing, layout
- A rule is a selector plus declarations
- Put CSS in a separate file linked from the page
---
## Same HTML, different look

HTML gives a page its structure. **CSS** (Cascading Style Sheets) gives it its look. The same HTML can look plain or polished depending on the CSS you apply.

## A rule

```css
h1 {
  color: #1e40af;
  font-size: 32px;
}
```

| Part | Name |
| --- | --- |
| `h1` | the **selector**: which elements to style |
| `color`, `font-size` | **properties**: what to change |
| `#1e40af`, `32px` | **values**: what to change it to |
| `property: value;` | a **declaration** |

## Three ways to add CSS

**1. A separate file (best):**

```html
<head>
  <link rel="stylesheet" href="style.css">
</head>
```

**2. A style block in the page:**

```html
<style>
  p { color: gray; }
</style>
```

**3. Inline on one element (avoid):**

```html
<p style="color: red;">Warning</p>
```

Use a separate file so one stylesheet can style the whole site, and so you can change the look in one place.

## The cascade

When several rules style the same element, CSS picks a winner:

1. A more **specific** selector beats a general one (an id beats a class, a class beats a tag).
2. If they are equally specific, the **later** rule wins.
3. Inline styles beat stylesheet rules.

```css
p { color: black; }
.note { color: blue; }   /* wins on <p class="note"> */
```

## Comments

```css
/* This is a CSS comment */
```

:::tip
Open your browser's developer tools (F12) and click an element. You can see every rule that applies to it, and edit them live. This is the fastest way to learn CSS.
:::
