---
title: What are AI agents?
summary: Understand how an agent differs from a chatbot and a fixed workflow, what parts it has, and when you should and should not build one.
takeaways:
- An agent is a model in a loop: it decides what to do, uses tools, looks at the result and decides again
- The parts are the model, tools, memory and a plan or instructions
- Start with the simplest design that works; many tasks do not need an agent
---
## From answering to acting

A chatbot **answers**. An **agent** **acts** to reach a goal: it can search, read files, call APIs, write code, and keep going until the job is done.

| | Chatbot | Workflow | Agent |
| --- | --- | --- | --- |
| Who decides the steps? | no steps, one reply | **you**, in fixed code | the **model**, at run time |
| Uses tools? | no | yes, in a set order | yes, whichever it chooses |
| Predictable? | yes | very | less so |
| Example | "What is RAG?" | extract text, then summarise, then email it | "Find three internships for me, check each deadline and draft the applications" |

## The agent loop

Every agent, however fancy, repeats the same cycle:

1. **Think**: look at the goal and everything seen so far.
2. **Act**: choose a tool and its inputs (or decide it is finished).
3. **Observe**: read the tool's result.
4. **Repeat** until the goal is met, or a limit is reached.

```py
goal -> [ model decides ] -> tool call -> result -> [ model decides ] -> tool call -> result -> ... -> final answer
```

The next lessons build this loop piece by piece, in code you can run.

## The parts of an agent

| Part | Role | Example |
| --- | --- | --- |
| **Model** | the "brain": reasons and picks actions | an LLM |
| **Instructions** | its role, rules and goal | "You are a study assistant. Never delete files." |
| **Tools** | what it can **do** | search the web, run SQL, read a PDF, send an email |
| **Memory** | what it can **remember** | the conversation, notes, past results |
| **Planning** | breaking a big goal into steps | "first find the dates, then compare" |
| **Guardrails** | limits and checks | step limits, permissions, human approval |

## Levels of autonomy

| Level | The agent... | Typical use |
| --- | --- | --- |
| **Assistant** | suggests, a human acts | code suggestions |
| **Supervised agent** | acts, but asks approval for important steps | drafting and sending emails |
| **Autonomous agent** | works alone for a long time | long research or coding tasks, with strong safeguards |

More autonomy means more value **and** more risk. Give an agent as little power as the job needs.

## Examples worth knowing

| Agent | What it does |
| --- | --- |
| coding agent | reads a codebase, edits files, runs tests, fixes failures |
| research agent | searches, reads sources, writes a cited summary |
| data analyst agent | writes and runs SQL or Python, explains the result |
| support agent | looks up an order, checks the policy, replies or escalates |
| study buddy | plans revision, quizzes you, tracks weak topics |

## When NOT to use an agent

| If the task is... | Better choice |
| --- | --- |
| one question and answer | a plain prompt |
| the same steps every time | a **workflow** (a fixed pipeline of calls) |
| needing exact, repeatable results | normal code |
| high-risk with no human check | do not automate it |
| easy to do with one retrieval call | RAG |

Agents are **slower, costlier and less predictable** than fixed code, because each loop turn is another model call that may go wrong. The usual advice: build the simplest thing first, add a tool, then add a loop only if the task truly needs the model to decide the steps.

:::tip
A good test: "Could I write the steps down in advance?" If yes, write a workflow in ordinary code. If the steps depend on what the model discovers along the way, an agent may be right.
:::
