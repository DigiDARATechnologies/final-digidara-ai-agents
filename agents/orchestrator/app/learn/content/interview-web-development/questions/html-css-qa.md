---
title: HTML and CSS questions
summary: Semantic HTML, the box model, specificity, Flexbox, Grid, positioning and responsive design.
kind: qa
takeaways:
- Use semantic tags and explain why
- Know the box model, specificity and positioning
- Explain Flexbox, Grid and media queries
---
### Q [Easy] What is semantic HTML and why use it?
Using tags that describe meaning (`header`, `nav`, `main`, `article`, `footer`) instead of generic `div`s. It improves accessibility, SEO and readability.

### Q [Easy] Block vs inline vs inline-block elements?
**Block** elements start on a new line and take full width (`div`, `p`). **Inline** elements sit within a line and ignore width and height (`span`, `a`). **Inline-block** sits in the line but accepts width and height.

### Q [Medium] Explain the CSS box model.
Every element is a box: **content**, then **padding**, **border** and **margin**. With `box-sizing: border-box`, width and height include padding and border, which makes sizing predictable.

### Q [Medium] What is CSS specificity?
The rule deciding which style wins. Order from strongest: inline style, then IDs, then classes, attributes and pseudo-classes, then element selectors. `!important` overrides, but avoid it.

### Q [Medium] `position`: static, relative, absolute, fixed, sticky?
**static**: normal flow. **relative**: offset from its normal place. **absolute**: positioned against the nearest positioned ancestor. **fixed**: positioned against the viewport. **sticky**: scrolls normally, then sticks at a set offset.

### Q [Medium] How does Flexbox work?
A one-dimensional layout. Set `display: flex` on the container; control direction with `flex-direction`, main-axis alignment with `justify-content` and cross-axis alignment with `align-items`; items can grow with `flex-grow`.

### Q [Medium] Flexbox vs Grid?
Flexbox lays out items in **one dimension** (a row or a column). Grid lays out in **two dimensions** (rows and columns together). Use Flexbox for components, Grid for page layouts, and combine them.

### Q [Medium] How do you make a site responsive?
Use a viewport meta tag, flexible units (`%`, `rem`, `fr`), Flexbox or Grid, **media queries** (`@media (max-width: 600px)`), responsive images and a **mobile-first** approach.

### Q [Medium] `em` vs `rem` vs `px`?
`px` is fixed. `em` is relative to the element's font size (can compound). `rem` is relative to the root font size, so it is predictable and good for scalable layouts.

### Q [Medium] How do you centre a div horizontally and vertically?
```css
.parent { display: flex; justify-content: center; align-items: center; }
```

### Q [Medium] What are pseudo-classes and pseudo-elements?
Pseudo-classes select a **state** (`:hover`, `:focus`, `:nth-child(2)`). Pseudo-elements style **part** of an element (`::before`, `::after`, `::first-line`).

### Q [Hard] What is the difference between `display: none` and `visibility: hidden`?
`display: none` removes the element from the layout. `visibility: hidden` hides it but it still takes up space.

### Q [Medium] What are `alt` text and ARIA used for?
`alt` describes images for screen readers and when images fail. ARIA attributes add accessibility information where HTML alone is not enough. Always start with correct semantic HTML.
