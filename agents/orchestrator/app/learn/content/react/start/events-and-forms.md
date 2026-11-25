---
title: Events and forms
summary: Handle clicks and typing, build controlled inputs, validate a form and submit it.
takeaways:
- Pass a function to onClick, onChange and onSubmit; do not call it
- A controlled input gets its value from state and updates state on change
- Call event.preventDefault() on submit to stop the page reloading
---
## Handling events

Attach a **function** to an event prop. Pass the function, do not call it:

```jsx
<>
  <button onClick={handleSave}>Save</button>              {/* correct: React calls it on click */}
  <button onClick={handleSave()}>Save</button>            {/* wrong: runs immediately while rendering */}
  <button onClick={() => remove(item.id)}>Delete</button> {/* use an arrow to pass arguments */}
</>
```

The handler receives an **event object**: `event.target.value` for inputs, `event.preventDefault()` to stop default browser behaviour.

## Controlled inputs

In a **controlled input**, React state is the single source of truth: the input shows the state, and typing updates the state.

```jsx
import { useState } from "react";

export default function App() {
  const [name, setName] = useState("Asha");

  return (
    <form>
      <label>
        Your name
        <input value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <p>Hello, {name || "stranger"}!</p>
    </form>
  );
}
```

```output
<form>
<label>Your name<input value="Asha"/></label><p>Hello, Asha!</p>
</form>
```

Every keystroke runs `onChange`, which sets the state, which re-renders with the new value. Because the state always knows the current text, validation, formatting and clearing the field are easy.

## A complete form

```jsx
import { useState } from "react";

function validate(values) {
  const errors = {};
  if (values.name.trim().length < 2) errors.name = "Enter at least 2 letters.";
  if (!/^\S+@\S+\.\S+$/.test(values.email)) errors.email = "Enter a valid email.";
  return errors;
}

export default function App() {
  const [values, setValues] = useState({ name: "", email: "" });
  const [touched, setTouched] = useState({ name: true, email: true });
  const errors = validate(values);

  function handleChange(event) {
    setValues({ ...values, [event.target.name]: event.target.value });   // one handler for all fields
  }

  function handleSubmit(event) {
    event.preventDefault();                       // stop the page reload
    if (Object.keys(errors).length === 0) console.log("send", values);
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <input name="name" value={values.name} onChange={handleChange} placeholder="Name" />
      {touched.name && errors.name && <p role="alert">{errors.name}</p>}
      <input name="email" value={values.email} onChange={handleChange} placeholder="Email" />
      {touched.email && errors.email && <p role="alert">{errors.email}</p>}
      <button type="submit" disabled={Object.keys(errors).length > 0}>Sign up</button>
    </form>
  );
}
```

```output
<form noValidate="">
<input placeholder="Name" name="name" value=""/><p role="alert">Enter at least 2 letters.</p>
<input placeholder="Email" name="email" value=""/><p role="alert">Enter a valid email.</p>
<button type="submit" disabled="">Sign up</button>
</form>
```

With empty fields, both errors show and the button is disabled (we pre-set `touched` to true so you can see them). The trick `[event.target.name]: value` uses the input's `name` attribute to update the right field with one handler.

## Other form controls

| Control | Value comes from |
| --- | --- |
| text, email, textarea | `value` + `onChange` and `e.target.value` |
| checkbox | `checked` + `onChange` and `e.target.checked` |
| select | `value` + `onChange` (set `value` on `<select>` itself) |
| radio | `checked={choice === "a"}` for each option |
| file | read `e.target.files[0]`; file inputs are always uncontrolled |

## Controlled versus uncontrolled

An **uncontrolled** input keeps its own value in the browser, and you read it when needed (with a `ref` or `FormData`). It is less code for simple forms:

```jsx
function handleSubmit(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget));   // { name: "...", email: "..." }
  save(data);
}
```

Use controlled inputs when you need live validation or to react to each keystroke; use uncontrolled for simple submit-only forms. Big forms often use a library such as **React Hook Form**.

:::tip
Always give a `<label>` to each input (wrapping it, or with `htmlFor` and `id`). It makes the form usable with a screen reader and gives a bigger click target.
:::
