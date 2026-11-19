---
title: Responsive design
summary: Make one page work on phones and desktops with the viewport tag, flexible sizes and media queries.
takeaways:
- Add the viewport meta tag first
- Use flexible units and max-width, not fixed pixel widths
- Media queries change the style at chosen screen widths
---
## One page, every screen

Most visitors use a phone. A **responsive** page adapts to the screen instead of needing a separate mobile site.

## Step 1: the viewport tag

Put this in the `<head>`. Without it phones pretend to be a wide desktop and shrink everything:

```html
<meta name="viewport" content="width=device-width, initial-scale=1">
```

## Step 2: flexible sizes

```css
img {
  max-width: 100%;   /* never wider than its container */
  height: auto;
}

.container {
  width: 90%;
  max-width: 1100px;
  margin: 0 auto;
}
```

Use percentages, `rem` and `max-width` rather than fixed pixel widths for layout.

| Unit | Meaning |
| --- | --- |
| `px` | a fixed pixel |
| `%` | a share of the parent |
| `rem` | a multiple of the root font size (usually 16px) |
| `vh`, `vw` | a share of the screen height or width |

## Step 3: media queries

A media query applies styles only when a condition is true:

```css
.cards {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

@media (max-width: 600px) {
  .cards {
    flex-direction: column;
  }
  h1 {
    font-size: 24px;
  }
}
```

Below 600px wide the cards stack in a column and the heading shrinks.

## Mobile first

Write the **phone** style first, then add rules for larger screens:

```css
.menu { display: none; }

@media (min-width: 768px) {
  .menu { display: flex; }
}
```

Starting small keeps the base CSS simple and fast on slow phones.

:::remember
Test in your browser: press F12, then Ctrl+Shift+M to switch to the device view and try different phone sizes.
:::

:::interview
**Interviewers often ask:** "What is mobile-first design?" Writing the base styles for small screens and using `min-width` media queries to add features for larger ones.
:::
