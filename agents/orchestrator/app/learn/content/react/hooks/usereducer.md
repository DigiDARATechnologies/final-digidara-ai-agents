---
title: useReducer
summary: Manage complex state with a reducer function, and see when it beats several useState calls.
takeaways:
- A reducer is a pure function (state, action) that returns the next state
- dispatch(action) describes what happened; the reducer decides the result
- Reach for useReducer when state has several parts that change together
---
## When useState gets messy

A shopping cart has items, a coupon and a status, with many ways to change them. Scattered `setState` calls make the logic hard to follow. **useReducer** puts all the update logic in **one place**.

## The reducer

A **reducer** takes the current state and an **action** and returns the **next state**. It must be pure: no fetching, no mutation, no randomness.

```jsx
import { useReducer } from "react";

function cartReducer(state, action) {
  switch (action.type) {
    case "add": {
      const existing = state.items.find((i) => i.id === action.item.id);
      const items = existing
        ? state.items.map((i) => (i.id === action.item.id ? { ...i, qty: i.qty + 1 } : i))
        : [...state.items, { ...action.item, qty: 1 }];
      return { ...state, items };
    }
    case "remove":
      return { ...state, items: state.items.filter((i) => i.id !== action.id) };
    case "coupon":
      return { ...state, coupon: action.code };
    case "clear":
      return initialCart;
    default:
      throw new Error("Unknown action: " + action.type);
  }
}

const initialCart = { items: [], coupon: null };

// run the reducer by hand to see how the state changes
let state = initialCart;
state = cartReducer(state, { type: "add", item: { id: 1, name: "Pen", price: 10 } });
state = cartReducer(state, { type: "add", item: { id: 1, name: "Pen", price: 10 } });
state = cartReducer(state, { type: "add", item: { id: 2, name: "Book", price: 120 } });
state = cartReducer(state, { type: "coupon", code: "SAVE10" });

export default function App() {
  const total = state.items.reduce((sum, i) => sum + i.price * i.qty, 0);
  return (
    <div>
      <ul>{state.items.map((i) => <li key={i.id}>{i.name} x {i.qty}</li>)}</ul>
      <p>Coupon: {state.coupon}</p>
      <p>Total: {total}</p>
    </div>
  );
}
```

```output
<div>
<ul>
<li>Pen x 2</li>
<li>Book x 1</li>
</ul>
<p>Coupon: SAVE10</p>
<p>Total: 140</p>
</div>
```

Because a reducer is a plain function, you can test it without React, as we just did by calling it directly: three `add` actions produced two lines, with the Pen's quantity at 2.

## Using it in a component

```jsx
function Cart() {
  const [state, dispatch] = useReducer(cartReducer, initialCart);

  return (
    <div>
      <button onClick={() => dispatch({ type: "add", item: { id: 1, name: "Pen", price: 10 } })}>
        Add pen
      </button>
      {state.items.map((i) => (
        <p key={i.id}>
          {i.name} x {i.qty}
          <button onClick={() => dispatch({ type: "remove", id: i.id })}>Remove</button>
        </p>
      ))}
    </div>
  );
}
```

Components only say **what happened** (`dispatch({ type: "remove", id })`). The rules for what that means live in the reducer.

## useState or useReducer?

| Choose `useState` when | Choose `useReducer` when |
| --- | --- |
| one simple value (a toggle, a text field) | several values that change together |
| few ways to update | many kinds of update |
| logic is trivial | the next state depends on rules you want to test |

## Reducer plus context

For app-wide state, put `state` and `dispatch` in context. Components anywhere can read the state or dispatch actions, and `dispatch` itself never changes identity, so components that only dispatch do not re-render needlessly:

```jsx
const CartStateContext = createContext(null);
const CartDispatchContext = createContext(null);

function CartProvider({ children }) {
  const [state, dispatch] = useReducer(cartReducer, initialCart);
  return (
    <CartStateContext.Provider value={state}>
      <CartDispatchContext.Provider value={dispatch}>{children}</CartDispatchContext.Provider>
    </CartStateContext.Provider>
  );
}
```

:::interview
**Interviewers often ask:** "Why must a reducer be pure?" React may call it more than once (Strict Mode does, to catch mistakes) and expects the same result for the same inputs. Side effects or mutation in a reducer would give wrong or duplicated results.
:::
