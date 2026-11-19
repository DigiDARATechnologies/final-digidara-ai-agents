---
title: Flexbox layout
summary: Arrange items in a row or column, space them out, and centre things with Flexbox.
takeaways:
- display: flex on the parent lays its children in a row
- justify-content works along the row; align-items across it
- gap puts space between items
---
## A layout tool for one direction

Flexbox lays items out along one line, a row or a column, and gives you control over spacing and alignment.

```html
<div class="row">
  <div>One</div>
  <div>Two</div>
  <div>Three</div>
</div>
```

```css
.row {
  display: flex;
  gap: 16px;
}
```

The parent (`.row`) is the **flex container**. Its children become **flex items** placed side by side.

## Main axis and cross axis

By default the main axis runs left to right.

| Property | On | What it does |
| --- | --- | --- |
| `flex-direction` | container | `row` (default) or `column` |
| `justify-content` | container | spaces items along the **main** axis |
| `align-items` | container | aligns items along the **cross** axis |
| `gap` | container | space between items |
| `flex-wrap` | container | lets items go to the next line |
| `flex` | item | how much an item grows |

## Spacing examples

```css
.nav {
  display: flex;
  justify-content: space-between;  /* logo left, links right */
  align-items: center;             /* vertically centred */
}
```

Values for `justify-content`: `flex-start`, `center`, `flex-end`, `space-between`, `space-around`.

## Centre anything

```css
.centre {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
}
```

That puts a child exactly in the middle of the screen, a task that used to be famously awkward.

## Letting items grow

```css
.sidebar { width: 240px; }
.content { flex: 1; }   /* takes all the remaining space */
```

## A wrapping card grid

```css
.cards {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}
.card {
  flex: 1 1 240px;   /* grow, shrink, start at 240px */
}
```

:::tip
Remember: **justify** is along the main axis, **align** is across it. If you switch to `flex-direction: column`, the two swap directions.
:::
