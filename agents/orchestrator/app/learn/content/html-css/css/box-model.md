---
title: The box model
summary: Every element is a box with content, padding, border and margin.
takeaways:
- Content, padding, border and margin make up every box
- Padding is inside the border; margin is outside
- box-sizing: border-box makes widths easier to predict
---
## Everything is a box

Every element on a page is a rectangular box with four layers, from the inside out:

| Layer | What it is |
| --- | --- |
| **Content** | the text or image itself |
| **Padding** | space between the content and the border |
| **Border** | a line around the padding |
| **Margin** | space between this box and its neighbours |

```css
.card {
  width: 300px;
  padding: 16px;
  border: 1px solid #cbd5e1;
  margin: 24px;
}
```

## Shorthand

```css
padding: 10px;                 /* all four sides */
padding: 10px 20px;            /* top and bottom, left and right */
padding: 5px 10px 15px 20px;   /* top, right, bottom, left (clockwise) */
margin: 0 auto;                /* no vertical margin, centred horizontally */
```

## The width surprise

By default, `width` is only the **content**. Padding and border are added on top, so a `300px` box with `16px` padding is really `332px` wide.

Fix that for the whole page:

```css
*, *::before, *::after {
  box-sizing: border-box;
}
```

With `border-box`, the width **includes** padding and border, so `300px` means 300px.

## Rounded corners and shadows

```css
.card {
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
```

## Display

| Value | Behaviour |
| --- | --- |
| `block` | takes the full width, starts on a new line (`div`, `p`, `h1`) |
| `inline` | flows within text, ignores width and height (`span`, `a`) |
| `inline-block` | flows within text but accepts width and height |
| `none` | not shown at all |

:::tip
To see the boxes, open developer tools (F12) and hover over an element: the padding and margin show in colour.
:::

:::interview
**Interviewers often ask:** "Explain the CSS box model." Content, padding, border, margin, from the inside out. Mention `box-sizing: border-box` and you will stand out.
:::
