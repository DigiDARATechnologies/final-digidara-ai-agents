---
title: Routing with React Router
summary: Build a multi-page app: routes, links, URL parameters, nested layouts, protected pages and a not-found route.
takeaways:
- A router shows different components for different URLs without reloading the page
- Use Link and NavLink, not plain anchors, for in-app navigation
- Nested routes with an Outlet share layouts; loaders and guards control access
---
## Single-page apps need a router

A React app is one HTML page. A **router** changes what is shown based on the URL, and updates the address bar and back button, without a full reload. **React Router** is the most widely used one.

```py
npm install react-router-dom
```

## Basic routes

```jsx
import { createBrowserRouter, RouterProvider, Link, NavLink, Outlet, useParams, useNavigate } from "react-router-dom";

function Layout() {
  return (
    <div>
      <nav>
        <NavLink to="/" end>Home</NavLink>
        <NavLink to="/courses">Courses</NavLink>
        <NavLink to="/about">About</NavLink>
      </nav>
      <main>
        <Outlet />          {/* the matching child route is drawn here */}
      </main>
    </div>
  );
}

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Home /> },
      { path: "courses", element: <Courses /> },
      { path: "courses/:slug", element: <CourseDetail /> },
      { path: "about", element: <About /> },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
```

- `Layout` appears on every page; the `Outlet` swaps in the page for the current URL.
- `NavLink` is a `Link` that knows when it is the active page, so you can style it.
- `path: "*"` matches anything else: your **404** page.

:::warning
Use `<Link to="/courses">`, not `<a href="/courses">`, for navigation inside your app. A plain `<a>` reloads the whole page and throws away all React state.
:::

## URL parameters and queries

```jsx
import { useParams, useSearchParams, useNavigate } from "react-router-dom";

function CourseDetail() {
  const { slug } = useParams();                              // from /courses/:slug
  const [search, setSearch] = useSearchParams();             // ?level=advanced
  const navigate = useNavigate();

  return (
    <div>
      <h1>{slug}</h1>
      <p>Level filter: {search.get("level") ?? "all"}</p>
      <button onClick={() => setSearch({ level: "advanced" })}>Show advanced</button>
      <button onClick={() => navigate("/courses")}>Back</button>
    </div>
  );
}
```

Keeping filters and pages in the URL means a user can **bookmark and share** exactly what they are looking at.

## Loaders: fetch before showing the page

React Router (data routers) can load data **before** rendering, instead of "render, then fetch in an effect":

```jsx
import { useLoaderData } from "react-router-dom";

async function courseLoader({ params }) {
  const res = await fetch(`/api/courses/${params.slug}`);
  if (!res.ok) throw new Response("Not found", { status: 404 });
  return res.json();
}

// in the route table:
// { path: "courses/:slug", element: <CourseDetail />, loader: courseLoader, errorElement: <CourseError /> }

function CourseDetail() {
  const course = useLoaderData();          // already loaded: no loading state needed here
  return <h1>{course.title}</h1>;
}
```

## Protected routes

```jsx
import { Navigate, Outlet, useLocation } from "react-router-dom";

function RequireAuth() {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;   // remember where they wanted to go
  return <Outlet />;
}

// { element: <RequireAuth />, children: [{ path: "dashboard", element: <Dashboard /> }] }
```

:::warning
A protected route only hides the **screen**. Anyone can still call your API directly. The server must check permissions on every request; client-side guards are for user experience, not security.
:::

## Code-split routes

Combine routing with `lazy` so each page's code downloads only when visited:

```jsx
const Reports = lazy(() => import("./pages/Reports"));
// { path: "reports", element: <Suspense fallback={<p>Loading...</p>}><Reports /></Suspense> }
```

## Checklist

| Need | Tool |
| --- | --- |
| links with an "active" style | `NavLink` |
| change page from code (after a save) | `useNavigate` |
| read `/:id` | `useParams` |
| read and set `?filter=` | `useSearchParams` |
| shared page layout | a layout route with `<Outlet />` |
| 404 page | `path: "*"` |
| errors per route | `errorElement` |

:::interview
**Interviewers often ask:** "How does client-side routing work?" The router intercepts navigation, updates the URL with the History API and renders the component matching the new path, without asking the server for a new HTML page. The server must still serve `index.html` for every path so a direct visit or refresh works.
:::
