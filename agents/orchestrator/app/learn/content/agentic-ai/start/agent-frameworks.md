---
title: Agent frameworks: LangGraph, CrewAI and the rest
summary: Know what agent frameworks give you, how the main ones differ, and when to use a framework and when plain code is better.
takeaways:
- A framework supplies the loop, tool handling, state and tracing so you write less plumbing
- Graph-style frameworks give control; role-style frameworks give speed; plain code gives clarity
- Start with plain code to understand the loop, then adopt a framework when the workflow grows
---
## What a framework gives you

You already built the loop by hand: send messages, run tools, feed results back. Frameworks package the common parts:

- the **agent loop** and stopping rules
- **tool** registration and argument validation
- **state** and memory between steps
- **retries**, timeouts and error handling
- **tracing** so you can see every step
- **human approval** pauses and resuming a run later

## The main styles

| Style | Examples | Idea | Good for |
| --- | --- | --- | --- |
| **Graph / state machine** | LangGraph | you draw nodes and edges; the model decides inside nodes | workflows needing control, branches, loops, approvals |
| **Role-based crews** | CrewAI, AutoGen | define agents with roles ("researcher", "writer") that talk | quick multi-agent prototypes |
| **Provider SDKs** | OpenAI Agents SDK, Claude Agent SDK | the model vendor's own tools, handoffs and guardrails | simple, well-supported agents on one provider |
| **Data / RAG focused** | LlamaIndex | agents built around your documents | knowledge-heavy assistants |
| **Plain code** | your own loop | a function and a `while` loop | small agents, learning, full control |

The names change quickly. The ideas (loop, tools, state, guardrails) stay the same, so learn those first.

## What a graph looks like

```python
# LangGraph style (shape only)
graph = StateGraph(State)
graph.add_node("plan", plan_step)
graph.add_node("search", search_step)
graph.add_node("write", write_step)
graph.add_node("review", review_step)

graph.add_edge("plan", "search")
graph.add_edge("search", "write")
graph.add_conditional_edges("review", lambda s: "write" if s["needs_fix"] else END)
```

The path is **designed by you**; the model only works inside each step. That predictability is why graphs are popular for production.

## Choosing

Ask these questions:

1. **Is the path fixed?** If the steps are always the same, use a plain workflow, no agent needed.
2. **Do I need approvals, retries or resuming?** Use a graph framework.
3. **Is it a quick demo with several roles?** A crew framework is fast.
4. **Am I on one model vendor?** Its SDK may be the simplest.
5. **Is it small?** Write it yourself; fewer moving parts.

## Cautions

- Frameworks hide detail. When something breaks you must understand the loop underneath.
- Versions change often; pin versions and read the changelog.
- More agents is not better. Each extra agent adds cost, delay and ways to fail.

:::interview Do you need a framework to build an agent?
No. An agent is a model, tools and a loop. A framework saves effort on state, tracing, retries and approvals as the system grows, but understanding the plain loop comes first.
:::
