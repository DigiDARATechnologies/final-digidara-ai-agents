---
title: Coding, browser and computer-use agents
summary: See how agents write and run code, browse the web and operate software, and the sandboxing and review needed to use them safely.
takeaways:
- Coding agents read files, edit code, run tests and iterate until the tests pass
- Browser and computer-use agents act through screenshots and clicks, so they are slower and riskier
- Always run them in a sandbox with limited permissions and review changes before they matter
---
## Coding agents

A coding agent is a normal agent whose tools are about code:

| Tool | Purpose |
| --- | --- |
| read / search files | understand the project |
| edit / write file | change code |
| run command | run tests, linters, the app |
| git | see changes, create a branch |

The loop that makes them effective:

```text
read the task -> explore the code -> make a change
   -> run the tests -> read the failures -> fix -> run again
   -> stop when tests pass (or the step limit is reached)
```

The key is the **feedback from running code**: a failing test is clear, honest information the model can act on. Agents are far more reliable when a good test suite exists.

Good habits when you use one:

- Give a **clear task** and the **definition of done** ("all tests pass, no new warnings").
- Work on a **branch** and read the diff before merging.
- Ask it to explain risky changes and to keep changes small.
- Never paste secrets into the chat or the code.

## Code interpreter agents

Some agents write and **run short programs** to do analysis: load a CSV, compute statistics, draw a chart. The model is not good at exact arithmetic, but a program is, so running code gives correct numbers. The code runs in a **sandbox**.

## Browser agents

A browser agent opens pages, reads them and clicks, types and scrolls. Two ways of seeing a page:

- **Page structure** (HTML or accessibility tree): faster and more exact.
- **Screenshots**: works on any site, but slower and less precise.

Typical uses: fill forms, collect information, test a website. Weaknesses: pages change, pop-ups confuse it, it is slow, and some sites block automation.

## Computer-use agents

These operate a whole desktop through screenshots, mouse and keyboard, so they can use apps that have no API. They are the most flexible and the most dangerous: a wrong click can delete or send something.

## Safety first

| Risk | Protection |
| --- | --- |
| Runs harmful commands | **sandbox** (container or virtual machine) with no access to your real files |
| Leaks secrets | keep keys out of the environment the agent can see |
| Reads a web page with hidden instructions | treat web content as untrusted data; **prompt injection** is real |
| Irreversible actions | require **human approval** for delete, send, pay and deploy |
| Runs up costs | step, time and money limits |
| Network misuse | allow only the sites it needs |

:::warning
Never give a browser or computer-use agent your logged-in accounts, bank sites or personal email. Use a separate, limited account and watch what it does.
:::

:::remember
The sandbox, the permissions and the human check matter more than how clever the agent is.
:::
