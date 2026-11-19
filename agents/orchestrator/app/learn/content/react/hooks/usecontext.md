---
title: useContext
summary: Share values such as the theme or the logged-in user across the tree without passing props through every level.
takeaways:
- Context passes data to any descendant without prop drilling
- Create a context, provide a value, and read it with useContext
- Every consumer re-renders when the value changes, so keep contexts small and focused
---
## Prop drilling

Imagine a `user` needed by a button deep in the tree. Passing it as a prop through every layer, including layers that do not care, is called **prop drilling**. **Context** lets a component far away read the value directly.

## Create, provide, consume

```jsx
import { createContext, useContext } from "react";

const ThemeContext = createContext("light");          // 1. create, with a default value

function ThemedButton({ children }) {
  const theme = useContext(ThemeContext);              // 3. read the nearest provided value
  return <button className={"btn btn-" + theme}>{children}</button>;
}

function Toolbar() {
  return (
    <div>
      <ThemedButton>Save</ThemedButton>                 {/* no theme prop passed */}
      <ThemedButton>Cancel</ThemedButton>
    </div>
  );
}

export default function App() {
  return (
    <ThemeContext.Provider value="dark">                {/* 2. provide a value to the subtree */}
      <Toolbar />
    </ThemeContext.Provider>
  );
}
```

```output
<div>
<button class="btn btn-dark">Save</button>                 <button class="btn btn-dark">Cancel</button>
</div>
```

The buttons are two levels below the provider and received no props, yet both picked up `dark`. Outside any provider, they would get the default, `light`. In React 19 you can write `<ThemeContext value="dark">` directly, without `.Provider`.

## A real pattern: auth context with a custom hook

Wrap the context in a provider component and a small hook, so the rest of the app never touches the raw context:

```jsx
import { createContext, useContext, useState } from "react";

const AuthContext = createContext(null);

function AuthProvider({ children, initialUser = null }) {
  const [user, setUser] = useState(initialUser);
  const value = { user, login: (u) => setUser(u), logout: () => setUser(null) };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

function useAuth() {
  const ctx = useContext(AuthContext);
  if (ctx === null) throw new Error("useAuth must be used inside <AuthProvider>");   // a helpful guard
  return ctx;
}

function Header() {
  const { user } = useAuth();
  return <header>{user ? `Signed in as ${user.name}` : "Guest"}</header>;
}

export default function App() {
  return (
    <div>
      <AuthProvider initialUser={{ name: "Asha" }}>
        <Header />
      </AuthProvider>
      <AuthProvider>
        <Header />
      </AuthProvider>
    </div>
  );
}
```

```output
<div>
<header>Signed in as Asha</header>
<header>Guest</header>
</div>
```

Two separate providers, two separate values. The guard in `useAuth` turns a confusing `undefined` error into a clear message if someone forgets the provider.

## The performance catch

When a context value changes, **every component that reads it re-renders**. Two habits keep this under control:

- **Split contexts** by concern (a `ThemeContext` and an `AuthContext`, not one giant `AppContext`).
- **Keep the value stable.** An object created inline, like `value={{ user, login }}`, is new on every render of the provider, so all consumers re-render each time. Wrap it in `useMemo` when the provider re-renders often.

```jsx
const value = useMemo(() => ({ user, login, logout }), [user]);
```

| Use context for | Avoid it for |
| --- | --- |
| theme, language, current user | data that changes many times a second |
| settings and feature flags | large frequently updated lists (use a state library) |
| values needed by many distant components | one or two levels of passing: props are simpler |

:::interview
**Interviewers often ask:** "What is prop drilling and how do you avoid it?" Passing props through components that only forward them. Avoid it with context for broadly shared values, with composition (passing children or elements), or with a state library.
:::
