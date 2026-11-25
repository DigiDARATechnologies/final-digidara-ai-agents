---
title: Human in the loop: approvals and handoffs
summary: Design the points where an agent stops and asks a person: approvals, confirmations, escalation and feedback.
takeaways:
- Let agents act freely on safe steps and ask a person before risky ones
- Show exactly what will happen so the approval is meaningful
- Learn from the person's corrections to improve over time
---
## Why keep a human involved

Agents make mistakes and can be tricked. A human check turns many serious failures into small, catchable ones. It also builds **trust**: people accept automation faster when they stay in control.

## Where to put the human

| Moment | Example |
| --- | --- |
| **Before a risky action** | approve sending an email, paying, deleting, deploying |
| **When the agent is unsure** | "I found two matching customers. Which one?" |
| **For ambiguous goals** | clarify before spending time |
| **After a draft** | review and edit before publishing |
| **On escalation** | hand a hard or angry case to a person |

## Classify actions by risk

| Risk | Examples | Policy |
| --- | --- | --- |
| **Low** | search, read, draft | allow automatically |
| **Medium** | create a record, schedule a meeting | allow, log, easy undo |
| **High** | send, pay, delete, change permissions, deploy | **require approval** |

## A good approval request

Be specific. Not "Allow this action?" but:

```text
The agent wants to send this email
To: principal@college.edu
Subject: Fee extension request for Ravi (2nd year)
Body: ... (full text)
[Approve] [Edit] [Reject]
```

The person must see **exactly** what will happen. Avoid asking so often that people click approve without reading (**approval fatigue**); ask only for meaningful steps.

## Pausing and resuming

The agent must be able to **stop, wait for hours**, then continue. That needs its state saved (the production lesson) and a clear record of who approved what.

```python
def run_step(action):
    if action.risk == "high":
        request_id = save_pending_approval(action)      # store, notify the person
        return {"status": "waiting_for_approval", "id": request_id}
    return execute(action)

def on_approval(request_id, approved, edited_action=None):
    action = load_pending(request_id)
    if approved:
        execute(edited_action or action)
```

## Escalation to a person

Define when the agent must stop: low confidence, repeated failure, an angry user, a sensitive topic, or something outside its tools. Pass the **full context** (summary, steps taken) so the person does not start over.

## Learn from the human

Record edits and rejections. They show where the agent is weak and become new test cases or examples for the prompt. Over time, as measured accuracy rises, you can **relax approvals** for the safe cases.

## Design rules

1. Default to asking for anything irreversible.
2. Make approvals **fast**: one screen, clear buttons, mobile friendly.
3. Always allow **undo** where possible.
4. Keep an **audit log**: who approved what, and when.

:::remember
Autonomy is earned. Start with approval on important actions, measure, then loosen where the data supports it.
:::
