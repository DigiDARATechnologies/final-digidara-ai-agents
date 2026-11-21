---
title: Agentic AI interview questions
summary: Common agentic AI questions with short answers: agents, tools, the loop, memory, multi-agent patterns, MCP, safety and evaluation.
kind: qa
takeaways:
- Explain the agent loop and tool calling in plain words
- Know when not to use an agent, and how to make one safe
- Be ready to discuss memory, multi-agent patterns, MCP and evaluation
---
### Q [Easy] What is an AI agent?
A system where a language model runs in a loop: it decides the next action, uses tools such as search, code or APIs, observes the result and continues until the goal is reached or a limit is hit. Unlike a chatbot, it acts to complete a task.

### Q [Easy] What is the difference between a chatbot, a workflow and an agent?
A chatbot answers a message. A workflow follows steps that you fixed in code, possibly calling a model at some steps. An agent lets the model decide the steps at run time. Agents are the most flexible and the least predictable.

### Q [Medium] How does tool (function) calling work?
You describe tools to the model with a name, description and input schema. The model replies with a structured request to call a tool. Your application validates the request, runs the real function, and returns the result to the model. The model never executes anything itself.

### Q [Medium] What is the ReAct pattern?
Reason and Act: the model alternates between reasoning about what to do next and taking an action (a tool call), then reads the observation and reasons again. It is the basic think, act, observe agent loop.

### Q [Medium] Why must an agent have a step limit?
Models can loop, repeat failing calls or never decide to finish. A maximum number of steps (plus token, cost and time budgets) stops runaway behaviour and bills.

### Q [Medium] How does an agent remember things?
The model has no memory between calls, so memory is built by the application: recent messages are kept in the prompt (trimmed or summarised to fit the context window), and long-term facts are stored in a database or vector store and retrieved when relevant.

### Q [Medium] When should you use a workflow instead of an agent?
When the steps are known in advance, the task repeats, results must be predictable, or cost and latency matter. Agents are justified when the next step depends on what the model discovers along the way.

### Q [Medium] What are the main multi-agent patterns?
Routing (a classifier sends a request to a specialist), supervisor and workers (a coordinator splits and checks tasks), pipelines (agents in sequence), parallel workers, critique or review loops, and hand-offs between agents. More agents add cost, latency and failure points, so use the fewest that work.

### Q [Medium] What is MCP?
The Model Context Protocol, an open standard for connecting AI applications to tools and data. A server exposes tools, resources and prompts, and a client in the host application connects to it, so one tool server works with many AI apps.

### Q [Hard] How do you make an agent safe?
Least privilege for tools and data, read and write separated, deny by default, human approval for risky actions, budgets and step limits, sandboxing for generated code, validation of outputs, audit logs and traces, and tests with failing and hostile inputs.

### Q [Hard] What is prompt injection, and why is it worse for agents?
Untrusted text (a web page, email or document) can contain instructions the model follows. For a plain chatbot the damage is a bad answer; for an agent with tools it can trigger real actions such as leaking data or sending messages. Limit permissions, keep untrusted content away from powerful tools, require approval and monitor.

### Q [Hard] How do you evaluate an agent?
Build a test set of realistic tasks with success criteria, run each several times (results vary), and measure success rate, number of steps, cost, latency, and failure types. Include edge cases, tool failures and adversarial inputs, and review traces of failures.

### Q [Hard] Why do errors compound in multi-step agents?
If each step is 90% reliable, ten steps in sequence succeed only about 35% of the time. Reduce risk with fewer steps, verification between steps, tools for exact facts, and human checkpoints.

### Q [Medium] What makes a good tool for an agent?
One clear purpose, a precise description and well-typed parameters, short useful output, errors returned as readable messages, validation and limits inside the tool, and a clear separation between safe read tools and risky write tools.

### Q [Medium] How is an agent different from RAG?
RAG is one fixed pattern: retrieve passages, then answer from them. An agent can use RAG as one tool among many and decides when to call it, in what order, and what to do with the result.

:::practice mock-interview
Explain the agent loop and how you would make a support agent safe, aloud in a Mock Interview.
:::
