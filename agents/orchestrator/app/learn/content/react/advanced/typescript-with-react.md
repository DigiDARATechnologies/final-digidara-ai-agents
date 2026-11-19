---
title: TypeScript with React
summary: Type props, state, events, refs and hooks so mistakes show up in your editor before users find them.
takeaways:
- Type props with an interface or type alias; most other types are inferred
- Type state when the starting value does not show the full shape
- Use discriminated unions to make impossible states impossible
---
## Why TypeScript

TypeScript catches errors while you type: a missing prop, a misspelt field, `undefined` used as a number. In a big React app it also acts as living documentation, since a component's props **are** its contract.

Start a project with it: `npm create vite@latest my-app -- --template react-ts`.

## Typing props

```jsx
type CourseCardProps = {
  title: string;
  lessons: number;
  level?: "Beginner" | "Intermediate" | "Advanced";      // optional, and limited to three values
  onOpen: (slug: string) => void;
  children?: React.ReactNode;
};

function CourseCard({ title, lessons, level = "Beginner", onOpen, children }: CourseCardProps) {
  return (
    <article>
      <h3>{title}</h3>
      <p>{lessons} lessons · {level}</p>
      <button onClick={() => onOpen(title.toLowerCase())}>Open</button>
      {children}
    </article>
  );
}

// <CourseCard title="Python" lessons="15" />      ← error: "15" is a string, not a number
// <CourseCard title="Python" lessons={15} />      ← error: onOpen is missing
// <CourseCard level="Expert" ... />               ← error: not one of the three levels
```

Your editor now flags all three mistakes as you type, before the code ever runs.

## Typing state

TypeScript **infers** simple state. Give it a type when it cannot know the shape:

```jsx
const [count, setCount] = useState(0);                          // inferred as number
const [name, setName] = useState("");                           // inferred as string

type User = { id: number; name: string; email: string };
const [user, setUser] = useState<User | null>(null);            // starts empty, later a User
const [items, setItems] = useState<string[]>([]);               // an empty array needs a type
```

When state can be `null`, TypeScript makes you handle it:

```jsx
return <p>{user ? user.name : "Not signed in"}</p>;      // user.name alone would be an error
```

## Typing events and refs

```jsx
function SearchBox() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");

  function handleChange(event: React.ChangeEvent<HTMLInputElement>) {
    setText(event.target.value);
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    inputRef.current?.focus();            // current may be null, so use ?.
  }

  return (
    <form onSubmit={handleSubmit}>
      <input ref={inputRef} value={text} onChange={handleChange} />
    </form>
  );
}
```

Hovering over an inline handler, such as `onChange={(e) => ...}`, shows the inferred event type; usually you do not need to write it.

## Discriminated unions: no impossible states

Instead of three loose variables (`loading`, `error`, `data`) that could contradict each other, model the states:

```jsx
type Request<T> =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "done"; data: T };

function Courses({ request }: { request: Request<{ id: number; title: string }[]> }) {
  switch (request.status) {
    case "loading":
      return <p>Loading...</p>;
    case "error":
      return <p role="alert">{request.message}</p>;     // message exists only in this branch
    case "done":
      return <ul>{request.data.map((c) => <li key={c.id}>{c.title}</li>)}</ul>;   // data only here
  }
}
```

TypeScript narrows the type inside each branch, so you cannot read `data` while loading. The same trick fits reducer actions: `{ type: "add"; item: Item } | { type: "remove"; id: number }`.

## Typing custom hooks and context

```jsx
function useLocalStorage<T>(key: string, initial: T): [T, (value: T) => void] {
  const [value, setValue] = useState<T>(() => {
    const saved = localStorage.getItem(key);
    return saved ? (JSON.parse(saved) as T) : initial;
  });
  useEffect(() => localStorage.setItem(key, JSON.stringify(value)), [key, value]);
  return [value, setValue];
}

const [theme, setTheme] = useLocalStorage("theme", "light");     // T is inferred as string

type AuthValue = { user: User | null; login: (u: User) => void; logout: () => void };
const AuthContext = createContext<AuthValue | null>(null);

function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");   // narrows null away
  return ctx;
}
```

## Useful built-in types

| Type | For |
| --- | --- |
| `React.ReactNode` | anything renderable (`children`) |
| `React.ComponentProps<"button">` | all props of a native element |
| `React.ChangeEvent<HTMLInputElement>` | input change events |
| `React.MouseEvent<HTMLButtonElement>` | click events |
| `React.CSSProperties` | an inline `style` object |
| `Partial<T>`, `Pick<T, K>`, `Omit<T, K>` | build new types from existing ones |

Extend a native element's props so your wrapper accepts everything a button does:

```jsx
type ButtonProps = React.ComponentProps<"button"> & { variant?: "primary" | "ghost" };

function Button({ variant = "primary", className = "", ...rest }: ButtonProps) {
  return <button className={`btn btn-${variant} ${className}`} {...rest} />;
}
```

:::tip
Avoid `any`: it switches the checks off for everything it touches. If a type is unknown, use `unknown` and narrow it, or write a proper type. Turn on `"strict": true` in `tsconfig.json` from day one.
:::

:::note
TypeScript types disappear when the code is built; they do not check data coming from the network at run time. Validate API responses with a library such as **Zod** if you cannot trust the server.
:::
