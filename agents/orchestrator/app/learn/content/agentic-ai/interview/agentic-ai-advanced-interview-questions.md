---
title: Advanced agentic AI interview questions
summary: Deeper questions on agent patterns, tools, memory, safety, evaluation and production.
takeaways:
- Explain trade-offs and failure modes
- Show how you would test and limit an agent
- Use a concrete example from a project
kind: qa
---
### Q [Medium] What is the ReAct pattern?
The model alternates Thought, Action (tool call) and Observation, using each result to decide the next step until it can answer. It is flexible but needs step limits to avoid loops.

### Q [Medium] Plan-and-execute vs ReAct?
Plan-and-execute writes the full plan first and then runs the steps, which suits predictable multi-stage tasks and allows cheaper executors. ReAct decides step by step, which suits open-ended exploration.

### Q [Medium] What makes a good tool description?
A clear name, what it does, when to use it and when not to, typed parameters with examples, compact output and actionable error messages.

### Q [Medium] Single agent or multi-agent?
Start with one agent with good tools. Use several when roles, tools or context truly differ (supervisor, handoff, maker and checker), accepting extra cost and failure points.

### Q [Medium] Why do agents need memory, and what kinds exist?
Short-term memory is the conversation context; long-term memory stores facts and past results outside the prompt (a database or vector store) and retrieves them when relevant. Summarise to control context size.

### Q [Hard] What is the "lethal trifecta" for agents?
Access to private data, exposure to untrusted content, and a way to send data out. With all three, prompt injection can leak data. Remove at least one.

### Q [Hard] How do you make an agent safe to run in production?
Least-privilege tools, allow-lists, input and output validation in code, human approval for high-risk actions, step, time and cost limits, sandboxed execution, per-user permissions, full logging and a kill switch.

### Q [Hard] How do you evaluate an agent?
Build a task set with checkable success criteria, run each several times, measure success rate, tool correctness, steps, cost and safety, read traces to find the first wrong step, fix one thing at a time and rerun the whole set.

### Q [Hard] An agent loops forever. What do you check?
Missing step limit, tool errors the model cannot understand, vague tool descriptions, lost context, or no stop condition. Add limits and repeat detection, improve error messages, and summarise state.

### Q [Hard] How do you add human-in-the-loop to an agent?
Classify actions by risk, pause before high-risk ones and show exactly what will happen, save state so the run can resume after approval, log approvals, and escalate with full context when unsure.

### Q [Hard] What is MCP and why does it matter?
The Model Context Protocol is a standard way for agents to discover and call tools and data sources from servers, so one integration works across many clients. Treat third-party servers as untrusted and limit their permissions.

### Q [Hard] How do you reduce the cost and latency of an agent?
Fewer steps through better tools, smaller models for easy steps, shorter context, prompt and response caching, parallel tool calls, early stopping and budgets in code, measuring quality after each change.

### Q [Hard] Why use a graph framework such as LangGraph?
It gives explicit control over states, paths and loops, checkpointing for pausing and resuming, human approval points and traceability, which is valuable for reliable production workflows.
