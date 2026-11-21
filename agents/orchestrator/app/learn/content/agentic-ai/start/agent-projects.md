---
title: Agent projects you can build
summary: Four portfolio-ready agent projects with the architecture, build steps, tests and limits for each, and how to present them.
takeaways:
- Pick a small, real problem and a narrow set of tools
- Build in layers: prompt, then tools, then loop, then memory, then guardrails
- Test with real tasks and show your evaluation, not only a demo
---
## How to choose a project

| Good | Avoid |
| --- | --- |
| solves a problem you or your classmates really have | "an AI that does everything" |
| 2 to 4 simple tools | many tools you never tested |
| results you can check (a correct answer, a saved file) | outputs nobody can verify |
| a small, safe scope | agents that spend money or message strangers |

## Build in layers

| Layer | What you add | You can test it by |
| --- | --- | --- |
| 1. prompt | a clear role and rules | trying 10 questions |
| 2. tools | one function at a time, with validation | calling each tool without the model |
| 3. loop | the think, act, observe cycle with a step limit | reading the trace |
| 4. memory | trimming, summary, saved notes | long conversations |
| 5. guardrails | permissions, approval, budgets, logging | hostile and failing cases |
| 6. evaluation | a test set and a success rate | rerunning after each change |

## Project 1: Study buddy agent

**Goal:** helps a student plan and revise.

| Item | Detail |
| --- | --- |
| **Tools** | `get_exam_dates`, `read_my_notes` (RAG over the student's notes), `make_quiz`, `save_progress` |
| **Flow** | ask what the student needs, check the exam dates, find weak topics from saved progress, plan the week, quiz and record the scores |
| **Memory** | long-term: weak topics and preferences; short-term: the current session |
| **Test** | 15 sample students with different dates and weak topics; check that the plan covers every weak topic before its exam |
| **Limits** | it must not invent syllabus content: answers come from the notes with citations |

## Project 2: Resume and job-match agent

**Goal:** reviews a resume against a job description.

| Item | Detail |
| --- | --- |
| **Tools** | `read_resume` (PDF text), `read_job_description`, `extract_skills`, `suggest_improvements` |
| **Flow** | extract skills from both, find the gaps, rewrite weak bullets using the action and result formula, produce a checklist |
| **Output** | structured JSON (validated) plus a friendly summary |
| **Test** | 10 resumes and 5 job descriptions with known gaps |
| **Limits** | never invent experience; flag every suggestion as a suggestion; protect personal data |

## Project 3: Data analyst agent

**Goal:** answers questions about a CSV or a small database.

| Item | Detail |
| --- | --- |
| **Tools** | `list_columns`, `run_sql` (**read-only** user, row limit), `make_chart` |
| **Flow** | understand the question, look at the columns, write SQL, run it, check the result, explain in plain words |
| **Guardrails** | a read-only database user, a 1,000-row limit, a query timeout, block everything except `SELECT` |
| **Test** | 25 questions with known answers (check the numbers against your own queries) |
| **Limits** | show the SQL it ran, so a person can verify it |

## Project 4: Support agent with RAG

**Goal:** answers customer questions from the company's policies and looks up orders.

| Item | Detail |
| --- | --- |
| **Tools** | `search_policies` (RAG), `get_order_status`, `create_ticket` |
| **Flow** | classify the request (router), retrieve policy text, look up the order if needed, answer with citations, or escalate to a human |
| **Guardrails** | answers only from sources; refunds and account changes always go to a human; each customer sees only their own orders |
| **Test** | 40 real-style questions, including ones with no answer and ones that try to trick it |
| **Limits** | measure how often it escalates correctly |

## What recruiters want to see

| Show | Why |
| --- | --- |
| the **problem** and who it helps | purpose |
| a **diagram** of the loop, tools and memory | design thinking |
| your **test set and success rate** | rigour beyond a demo |
| **failure cases** and how you fixed them | honesty and learning |
| **guardrails** you added | responsibility |
| **cost per task** | practicality |
| a short **demo video** and a README | easy to review |

## A starter structure

```py
agent-project/
  README.md
  agent/
    loop.py           # the think, act, observe loop with limits
    tools.py          # tool functions with validation
    memory.py         # trimming, summary, saved notes
    guard.py          # permissions, approval, budget, audit log
  tests/
    test_tools.py     # tools tested without any model
    cases.json        # your evaluation questions and expected results
    run_eval.py       # runs every case and prints the success rate
  .env.example        # the names of the keys, never the keys
```

:::practice capstone-project
Choose one of these projects, share your plan with the Capstone Project agent, and ask it to challenge your tool list and your test set before you start coding.
:::
