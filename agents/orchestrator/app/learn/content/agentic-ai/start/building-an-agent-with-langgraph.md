---
title: Build an agent with LangGraph: a walkthrough
summary: Follow a complete example of a small support agent as a graph: state, nodes, conditional routing and a human approval pause.
takeaways:
- A graph has shared state, nodes (steps) and edges (what comes next)
- Conditional edges let the model's decision choose the path
- Checkpointing allows pausing for approval and resuming later
---
## What we will build

A support agent that: reads a request, **classifies** it, answers simple questions itself, and for a **refund** asks a human to approve before acting.

```text
START -> classify -> (question) -> answer -> END
                  -> (refund)   -> check_policy -> wait_for_approval -> issue_refund -> END
```

(Display only. Library names and details change between versions; read the current LangGraph documentation.)

## 1. Define the state

The state is a shared object every node reads and updates.

```python
from typing import TypedDict, Literal

class SupportState(TypedDict):
    message: str
    category: Literal["question", "refund", "unknown"]
    answer: str
    refund_amount: float
    approved: bool
```

## 2. Write the nodes

Each node is a normal function that receives the state and returns the changes.

```python
def classify(state: SupportState):
    label = llm_choose(state["message"], options=["question", "refund"])   # one LLM call
    return {"category": label}

def answer(state: SupportState):
    return {"answer": llm_answer(state["message"], tools=[search_handbook])}

def check_policy(state: SupportState):
    amount = lookup_order_amount(state["message"])     # a tool, not the model's guess
    return {"refund_amount": amount}

def issue_refund(state: SupportState):
    if state["approved"]:
        payment_api.refund(state["refund_amount"])
        return {"answer": "Your refund has been issued."}
    return {"answer": "Your refund request was declined."}
```

## 3. Connect them with edges

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

graph = StateGraph(SupportState)
graph.add_node("classify", classify)
graph.add_node("answer", answer)
graph.add_node("check_policy", check_policy)
graph.add_node("issue_refund", issue_refund)

graph.add_edge(START, "classify")
graph.add_conditional_edges("classify", lambda s: s["category"],
                            {"question": "answer", "refund": "check_policy", "unknown": "answer"})
graph.add_edge("answer", END)
graph.add_edge("check_policy", "issue_refund")
graph.add_edge("issue_refund", END)

app = graph.compile(checkpointer=MemorySaver(), interrupt_before=["issue_refund"])
```

- **Conditional edges** read the state and choose the next node.
- `interrupt_before=["issue_refund"]` **pauses** the graph before the risky step.
- The **checkpointer** saves the state at every step so the run can resume.

## 4. Run, pause and resume

```python
config = {"configurable": {"thread_id": "ticket-1042"}}

app.invoke({"message": "I want a refund for order ORD-1042"}, config)
# paused before issue_refund; a person reviews the amount in your admin screen

app.update_state(config, {"approved": True})      # the person clicked Approve
result = app.invoke(None, config)                 # resume from the saved state
print(result["answer"])
```

## Why use a graph

| Benefit | How |
| --- | --- |
| **Control** | you decide the possible paths; the model chooses within them |
| **Safety** | risky steps sit behind an approval pause |
| **Resumable** | state is saved, so crashes and waits are fine |
| **Debuggable** | each node is a clear step you can trace and test |
| **Testable** | test each node on its own |

## Tips

1. Put **decisions** in small LLM calls, and **facts** (prices, policies) in tools.
2. Keep each node focused and short.
3. Add a **step limit** and handle failures with retries or a fallback node.
4. Trace runs (LangSmith or logs) to see the path taken.

:::tip
Draw your graph on paper first. If you can draw the boxes and arrows, the code is straightforward.
:::
