---
title: Lists and tables
summary: Show items in ordered and unordered lists, and data in tables.
takeaways:
- ul is bullets, ol is numbers, li is each item
- A table is rows (tr) of cells (td or th)
- Use tables for data, not for page layout
---
## Lists

An unordered (bulleted) list:

```html
<ul>
  <li>HTML</li>
  <li>CSS</li>
  <li>JavaScript</li>
</ul>
```

An ordered (numbered) list:

```html
<ol>
  <li>Open the editor</li>
  <li>Write the code</li>
  <li>Run it</li>
</ol>
```

Lists can nest: put a whole `<ul>` inside an `<li>`.

## Tables

```html
<table>
  <thead>
    <tr>
      <th>Name</th>
      <th>Marks</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Asha</td>
      <td>92</td>
    </tr>
    <tr>
      <td>Ravi</td>
      <td>78</td>
    </tr>
  </tbody>
</table>
```

| Tag | Meaning |
| --- | --- |
| `<table>` | the whole table |
| `<tr>` | a row |
| `<th>` | a heading cell |
| `<td>` | a data cell |
| `<thead>`, `<tbody>` | groups the header rows and the body rows |

## Merging cells

```html
<td colspan="2">Spans two columns</td>
<td rowspan="2">Spans two rows</td>
```

:::warning
Do not use tables to arrange a whole page. That is what CSS layout (Flexbox and Grid) is for. Tables are for data that has rows and columns.
:::

:::tip
A table needs no borders from HTML. Add them with CSS in the next chapter: `border: 1px solid #ccc;`.
:::
