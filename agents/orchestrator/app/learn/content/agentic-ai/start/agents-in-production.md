---
title: Running agents in production
summary: Move an agent from a demo to a real service: durable state, queues, human approval, cost control, observability, versioning and a safe rollout.
takeaways:
- Production agents need saved state, so a crash or a pause does not lose the work
- Put approvals, budgets and timeouts in the code, not only in the prompt
- Log every run and roll out gradually, with an easy way to turn the agent off
---
## A demo and a product are different

A demo runs once on your laptop. A product runs for many users, for a long time, with failures. Things to add:

## 1. Save the state

Long tasks can take minutes or hours, and servers restart. Store the run in a database after **every step**: the goal, the messages, tool results and the current step. If anything fails, the agent **resumes** from the last saved step instead of starting again. Graph frameworks such as LangGraph call this a checkpoint.

## 2. Run work in the background

Do not hold a web request open for a long agent run. Use a **job queue** (Celery, a cloud queue) so the user starts a task, sees "in progress", and gets the result or a notification later. Show progress such as "searching, reading, writing".

## 3. Put limits in code

| Limit | Why |
| --- | --- |
| Maximum steps | stops infinite loops |
| Time limit | stops a stuck run |
| Token and money budget | stops a surprise bill |
| Tool call limits | stops hammering an API |
| Per-user rate limit | fair use |

The prompt can **ask** the model to behave; only code can **enforce** it.

## 4. Human in the loop

Classify actions by risk:

- **Read-only** (search, read): allow.
- **Reversible** (create a draft): allow and log.
- **Irreversible or external** (send email, pay, delete, deploy): pause and **ask a person**, showing exactly what will happen.

Store the approval and who gave it.

## 5. Idempotency

An agent may retry a step after a failure. Make actions safe to repeat: use a unique request id so "create order" run twice creates **one** order, not two.

## 6. Observability

Log for each run: id, user, goal, every step, tool inputs and outputs (with private data removed), tokens, cost, time and final result. Build a simple dashboard of success rate, cost per task, average steps and common errors. Alert on spikes.

## 7. Version everything

Prompt, tools, model name and settings together define behaviour. Give each combination a **version number**, store it in the log, and keep the evaluation results for each version. This lets you answer "which change made it worse?" and roll back quickly.

## 8. Roll out safely

1. Run the task set (previous lesson).
2. **Shadow mode**: the agent proposes, a person acts.
3. Release to a few users with approval on.
4. Relax approvals only where the data shows it is safe.
5. Keep a **kill switch** that disables the agent instantly.

## Checklist before launch

- state saved after each step and runs can resume
- step, time and cost limits enforced in code
- approval for risky actions
- least-privilege credentials, secrets not in prompts
- logging, dashboard and alerts
- evaluation set passing, versions recorded
- kill switch and a plan for failures

:::interview What changes when you move an agent to production?
State persistence and resumption, background execution, enforced limits and budgets, human approval for risky actions, idempotent tools, full tracing and monitoring, versioned prompts and a gradual rollout with a kill switch.
:::
