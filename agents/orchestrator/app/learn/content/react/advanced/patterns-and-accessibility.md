---
title: Patterns, error boundaries and accessibility
summary: Use compound components, error boundaries and portals, and make your app usable by everyone with keyboard and screen reader support.
takeaways:
- Compound components give flexible APIs; error boundaries stop one crash taking down the whole app
- Use semantic HTML first; add ARIA only where HTML cannot express the meaning
- Everything must work with a keyboard, and focus must be managed in dialogs
---
## Compound components

A group of components that work together and share state through context, like `<select>` and `<option>`:

```jsx
import { createContext, useContext, useState } from "react";

const TabsContext = createContext(null);

function Tabs({ defaultValue, children }) {
  const [value, setValue] = useState(defaultValue);
  return <TabsContext.Provider value={{ value, setValue }}><div>{children}</div></TabsContext.Provider>;
}

function Tab({ id, children }) {
  const { value, setValue } = useContext(TabsContext);
  return (
    <button role="tab" aria-selected={value === id} onClick={() => setValue(id)}>
      {children}
    </button>
  );
}

function Panel({ id, children }) {
  const { value } = useContext(TabsContext);
  return value === id ? <div role="tabpanel">{children}</div> : null;
}

export default function App() {
  return (
    <Tabs defaultValue="notes">
      <div role="tablist">
        <Tab id="notes">Notes</Tab>
        <Tab id="videos">Videos</Tab>
      </div>
      <Panel id="notes">Lesson notes here</Panel>
      <Panel id="videos">Video list here</Panel>
    </Tabs>
  );
}
```

```output
<div>
<div role="tablist">
<button role="tab" aria-selected="true">Notes</button>
<button role="tab" aria-selected="false">Videos</button>
</div>
<div role="tabpanel">Lesson notes here</div>
</div>
```

The user composes the layout freely (`Tab`, `Panel`, extra markup), while the parts coordinate behind the scenes. Only the active panel is rendered, and the active tab is marked with `aria-selected`.

## Error boundaries

If a component throws while rendering, React removes the **entire** app from the screen unless an **error boundary** catches it. An error boundary shows a fallback for its own subtree and keeps the rest of the page alive. Today they must be class components (or you can use the `react-error-boundary` package):

```jsx
import { Component } from "react";

class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };                              // switch to the fallback UI
  }

  componentDidCatch(error, info) {
    reportToMonitoring(error, info.componentStack);        // send it to Sentry or similar
  }

  render() {
    if (this.state.error) {
      return (
        <div role="alert">
          <p>Something went wrong in this section.</p>
          <button onClick={() => this.setState({ error: null })}>Try again</button>
        </div>
      );
    }
    return this.props.children;
  }
}

// one broken widget no longer blanks the whole page
<ErrorBoundary>
  <RecommendationsWidget />
</ErrorBoundary>
```

Error boundaries catch errors during rendering. They do **not** catch errors in event handlers or async code: use `try/catch` for those.

## Portals

A **portal** renders children somewhere else in the DOM, usually for modals and tooltips that must escape a parent with `overflow: hidden` or a low `z-index`:

```jsx
import { createPortal } from "react-dom";

function Modal({ children, onClose }) {
  return createPortal(
    <div className="backdrop" onClick={onClose}>
      <div role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>{children}</div>
    </div>,
    document.body
  );
}
```

Events still bubble through the **React tree**, so a click inside the portal reaches the React parent as if it were nested there.

## Accessibility (a11y)

About one in six people lives with a disability, and many more use a keyboard, a screen reader or a small screen in bright sunlight. Accessible apps are also better for everyone, and many organisations are required by law to provide them.

**1. Use semantic HTML first.**

```jsx
export default function App() {
  return (
    <div>
      <header>
        <nav aria-label="Main">
          <a href="/courses">Courses</a>
        </nav>
      </header>
      <main>
        <h1>Learning Hub</h1>
        <button type="button">Start</button>
      </main>
    </div>
  );
}
```

```output
<div>
<header><nav aria-label="Main">
<a href="/courses">Courses</a></nav>
</header>
<main><h1>Learning Hub</h1>
<button type="button">Start</button>
</main>
</div>
```

A real `<button>` is focusable, works with Enter and Space, and is announced as a button. A `<div onClick>` does none of these; you would have to rebuild them all.

| Do | Instead of |
| --- | --- |
| `<button>` | `<div onClick>` |
| `<a href>` for navigation | `<span onClick={navigate}>` |
| `<nav>`, `<main>`, `<header>` | a `<div>` for everything |
| one `<h1>`, headings in order | headings chosen for their size |
| `<label>` tied to each input | placeholder text as the only label |

**2. Name everything.** Icon-only buttons need a text name:

```jsx
<>
  <button aria-label="Close dialog"><svg aria-hidden="true" /></button>
  <img src="chart.png" alt="Bar chart: sales rose 20% in March" />
  <img src="divider.png" alt="" />                       {/* decorative: empty alt */}
</>
```

**3. Keyboard support.** Every action must work without a mouse: Tab moves focus, Enter and Space activate, Escape closes dialogs. Never remove the focus outline without providing a clear replacement.

**4. Manage focus in dialogs.** Move focus **into** the dialog when it opens, keep Tab inside it, close on Escape, and return focus to the button that opened it. The native `<dialog>` element does much of this for you.

**5. Announce changes.** For updates a screen reader would not otherwise notice (a saved message, a form error) use a live region:

```jsx
<>
  <p role="status" aria-live="polite">{saved ? "Saved." : ""}</p>      {/* polite: waits for a pause */}
  <p role="alert">{error}</p>                                        {/* assertive: interrupts */}
</>
```

**6. Colour and motion.** Text contrast of at least 4.5 to 1, never use colour as the only signal (add an icon or text for errors), and respect `prefers-reduced-motion`.

## Checking your work

| Tool | Finds |
| --- | --- |
| `eslint-plugin-jsx-a11y` | missing alt text, clickable divs, bad labels, while you code |
| **axe DevTools** or Lighthouse | many contrast and ARIA problems in the browser |
| keyboard only | put the mouse away and use the whole app |
| a screen reader | NVDA (Windows, free) or VoiceOver (Mac): listen to one page |

:::warning
The first rule of ARIA is **do not use ARIA** if a native HTML element already does the job. Wrong ARIA is worse than none, because it tells assistive technology something untrue about your page.
:::

:::interview
**Interviewers often ask:** "How do you make a React app accessible?" Semantic HTML, labels and alt text, full keyboard support, managed focus in dialogs, live regions for dynamic messages, enough contrast, and testing with linting, axe and a real screen reader.
:::
