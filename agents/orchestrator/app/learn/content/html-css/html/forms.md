---
title: Forms
summary: Collect input with form, input, label, select, textarea and button.
takeaways:
- A form groups inputs and sends them somewhere
- Every input needs a label
- The type attribute changes what an input accepts
---
## Collecting input

```html
<form action="/signup" method="post">
  <label for="name">Name</label>
  <input type="text" id="name" name="name" required>

  <label for="email">Email</label>
  <input type="email" id="email" name="email" required>

  <button type="submit">Sign up</button>
</form>
```

- `action` is where the data is sent, and `method` is how (`get` or `post`).
- `name` is the key the server receives. Without it the value is not sent.
- `required` stops the form being sent while the field is empty.

## Labels

A `<label>` is linked to an input by `for` matching the input's `id`. Clicking the label focuses the input, and screen readers read it out. Every input should have one.

## Common input types

| Type | Gives you |
| --- | --- |
| `text` | one line of text |
| `email` | text that must look like an email |
| `password` | hidden characters |
| `number` | a number, with min and max |
| `date` | a date picker |
| `checkbox` | tick on or off |
| `radio` | choose one of a group (same `name`) |
| `file` | choose a file to upload |

## Other controls

```html
<select name="course">
  <option value="python">Python</option>
  <option value="sql">SQL</option>
</select>

<textarea name="message" rows="4"></textarea>

<input type="checkbox" id="agree" name="agree">
<label for="agree">I agree to the terms</label>
```

## Built-in checks

HTML can check some things for you: `required`, `minlength`, `maxlength`, `min`, `max` and `pattern`.

```html
<input type="number" name="age" min="18" max="60">
```

:::warning
Browser checks are only a convenience. Anyone can bypass them, so the **server must always check the data again**.
:::

:::interview
**Interviewers often ask:** "GET versus POST?" GET puts the data in the URL and is for reading or searching. POST sends it in the request body and is for changing data, such as signing up or paying.
:::
