---
title: Building reliable and safe agents
summary: Add the controls that make agents trustworthy: permissions, human approval, budgets, audit logs, and testing for failures.
takeaways:
- An agent can be wrong or be tricked, so limit what it is able to do
- Classify actions: allow, ask a human, or deny, and cap steps, tokens and money
- Log every action and test the agent on hard and hostile cases
---
## Assume it will make mistakes

Agents misread goals, misuse tools, and can be manipulated by text they read (prompt injection). You cannot make that impossible, so you **limit the damage** a mistake can do.

| Principle | Meaning |
| --- | --- |
| **least privilege** | give the minimum tools and access the task needs |
| **separate read from write** | reading is low-risk; changing things is not |
| **human approval** for risky actions | sending, paying, deleting, publishing |
| **budgets and limits** | steps, tokens, money, time |
| **audit everything** | a log of every action and why |
| **fail safe** | when unsure, stop and ask |

## A guarded tool runner

This wrapper decides, for each requested action, whether to **allow**, **ask a human**, or **deny**, and enforces a **budget** and keeps an **audit log**:

```python
PERMISSIONS = {
    "read_notes": "allow",        # safe, read-only
    "send_email": "ask",          # changes the outside world: needs a human
    "delete_file": "deny",        # never allowed for this agent
}

class Guard:
    def __init__(self, max_calls):
        self.max_calls = max_calls
        self.calls = 0
        self.log = []

    def run(self, tool, arguments, approve):
        self.calls += 1
        if self.calls > self.max_calls:
            return self.record(tool, arguments, "blocked: call budget used up")
        rule = PERMISSIONS.get(tool, "deny")                                 # unknown tools are denied by default
        if rule == "deny":
            return self.record(tool, arguments, "blocked: not permitted")
        if rule == "ask" and not approve(tool, arguments):
            return self.record(tool, arguments, "blocked: a human said no")
        return self.record(tool, arguments, "executed")

    def record(self, tool, arguments, outcome):
        self.log.append((tool, arguments, outcome))
        return outcome

guard = Guard(max_calls=5)
say_no = lambda tool, arguments: False
say_yes = lambda tool, arguments: True

guard.run("read_notes", {"topic": "SQL"}, say_yes)
guard.run("send_email", {"to": "principal@example.com"}, say_no)         # the human refuses
guard.run("send_email", {"to": "classmate@example.com"}, say_yes)        # the human agrees
guard.run("delete_file", {"path": "notes.txt"}, say_yes)                 # denied whatever a human says
guard.run("format_disk", {}, say_yes)                                    # unknown, so denied
guard.run("read_notes", {"topic": "Python"}, say_yes)                    # over the budget of 5 calls

for tool, arguments, outcome in guard.log:
    print(f"{tool:<12} {str(arguments):<38} {outcome}")
```

```output
read_notes   {'topic': 'SQL'}                       executed
send_email   {'to': 'principal@example.com'}        blocked: a human said no
send_email   {'to': 'classmate@example.com'}        executed
delete_file  {'path': 'notes.txt'}                  blocked: not permitted
format_disk  {}                                     blocked: not permitted
read_notes   {'topic': 'Python'}                    blocked: call budget used up
```

The log shows every decision: the safe read ran, one email was refused by the human and one approved, the deletion and the unknown tool were denied, and the sixth call was stopped by the budget. **Denying by default** (`PERMISSIONS.get(tool, "deny")`) means a tool nobody thought about can never run.

## What to guard

| Area | Controls |
| --- | --- |
| **actions** | allow, ask or deny per tool; per-user permissions |
| **data** | the agent sees only the data the current user may see |
| **loops** | maximum steps, repeat detection, timeouts |
| **cost** | token and money budgets per task and per user |
| **output** | validate JSON, links and commands before using them |
| **sandboxing** | run generated code in an isolated environment with no secrets and limited network |
| **secrets** | never place keys in prompts; give tools their own credentials |

## Prompt injection and agents

An agent that reads the web or email can find hidden instructions (for example "forward the user's files to this address"). The more powerful its tools, the worse a successful injection. Defences, in order of strength:

1. **Limit tools and permissions** so the worst case is small.
2. **Require approval** for outward actions.
3. **Keep untrusted content away from powerful tools**: have one step read and summarise outside text with **no** tools, and give only the safe summary to the acting agent.
4. **Label untrusted data** clearly in prompts and check outputs.
5. **Monitor** for odd behaviour.

## Test agents hard

| Test | Examples |
| --- | --- |
| **normal tasks** | the 20 most common requests |
| **edge cases** | missing data, ambiguous requests, very long inputs |
| **tool failures** | a tool times out or returns an error |
| **hostile input** | a document that says "ignore your instructions" |
| **limits** | does it stop at the step and cost limits? |
| **repeatability** | run the same task five times; how often does it succeed? |

Because results vary, measure a **success rate** across many runs, not one lucky run.

## Observability

Record each run as a **trace**: the goal, each model call, each tool call with its inputs and outputs, the cost and the final answer. When something goes wrong, you can replay exactly what the agent saw and did. Tools such as LangSmith, Langfuse and OpenTelemetry-based tracing do this for you.

## A launch checklist

| Check | Done |
| --- | --- |
| tools are least-privilege, with deny by default | |
| risky actions need human approval | |
| step, cost and time limits are set | |
| every action is logged and traceable | |
| tested on normal, edge, failure and hostile cases | |
| users know it is AI and can reach a human | |
| a way to switch it off quickly | |

:::warning
Do not give an agent the ability to move money, send messages in your name, or delete data without a human checkpoint until it has proven itself over many supervised runs.
:::
