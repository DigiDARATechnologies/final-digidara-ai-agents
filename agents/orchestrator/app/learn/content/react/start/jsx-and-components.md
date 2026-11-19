---
title: JSX and components
summary: Write markup inside JavaScript with JSX, embed values with curly braces, and learn the rules that trip up beginners.
takeaways:
- JSX looks like HTML but is JavaScript; a component returns one root element
- Curly braces embed any JavaScript expression
- Component names start with a capital letter; attributes are camelCase (className, htmlFor)
---
## JSX in one minute

**JSX** lets you write markup next to your logic. A build tool turns it into plain JavaScript function calls. It is not HTML, so a few rules differ.

```jsx
export default function App() {
  const name = "Asha";
  const marks = [92, 88, 79];
  const average = marks.reduce((a, b) => a + b, 0) / marks.length;

  return (
    <section className="card">
      <h2>{name.toUpperCase()}</h2>
      <p>Average: {average.toFixed(1)}</p>
      <p>Highest: {Math.max(...marks)}</p>
      <label htmlFor="email">Email</label>
      <input id="email" type="email" defaultValue="asha@example.com" />
    </section>
  );
}
```

```output
<section class="card">
<h2>ASHA</h2>
<p>Average: 86.3</p>
<p>Highest: 92</p>
<label for="email">Email</label><input id="email" type="email" value="asha@example.com"/></section>
```

Anything inside `{ }` is a JavaScript **expression**: a variable, a calculation, a function call. You cannot put statements such as `if` or `for` in there.

## The rules

| Rule | Example |
| --- | --- |
| Return **one** root element | wrap siblings in a `<div>` or a fragment `<>...</>` |
| Close every tag | `<img />`, `<input />`, `<br />` |
| `class` becomes `className` | `<div className="card">` |
| `for` becomes `htmlFor` | `<label htmlFor="email">` |
| Attributes are camelCase | `onClick`, `tabIndex`, `maxLength` |
| Component names start with a **capital** | `<Card />` is a component; `<card />` is an unknown HTML tag |
| Styles are objects | `style={{ color: "teal", fontSize: 18 }}` |

## Fragments

If you do not want an extra wrapper element, use a **fragment**:

```jsx
function Row() {
  return (
    <>
      <td>Asha</td>
      <td>92</td>
    </>
  );
}

export default function App() {
  return (
    <table>
      <tbody>
        <tr>
          <Row />
        </tr>
      </tbody>
    </table>
  );
}
```

```output
<table>
<tbody>
<tr>
<td>Asha</td><td>92</td></tr>
</tbody>
</table>
```

The `<td>` cells sit directly inside the `<tr>`, with no extra `<div>` breaking the table.

## Styles and classes

```jsx
export default function App() {
  const done = true;
  return (
    <p className={done ? "task done" : "task"} style={{ color: "teal", fontSize: 18 }}>
      Finish the lesson
    </p>
  );
}
```

```output
<p class="task done" style="color:teal;font-size:18px">Finish the lesson</p>
```

`style` takes an **object**, so the outer braces say "JavaScript here" and the inner braces are the object. CSS names become camelCase (`fontSize`), and plain numbers get `px`.

## Safe by default

React **escapes** every value you put in `{ }`, so text from a user cannot become HTML:

```jsx
export default function App() {
  const comment = "<script>alert('hacked')</script>";
  return <p>{comment}</p>;
}
```

```output
<p>&lt;script&gt;alert(&#x27;hacked&#x27;)&lt;/script&gt;</p>
```

The script tag is printed as harmless text. The escape hatch, `dangerouslySetInnerHTML`, is named that way for a reason: only use it with HTML you trust or have sanitised.

:::warning
Beginners often write `<Card/>` as `<card/>`. Lowercase names are treated as built-in HTML tags, so nothing of yours renders and there is no error. Always capitalise component names.
:::
