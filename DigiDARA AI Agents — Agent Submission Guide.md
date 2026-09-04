# DigiDARA AI Agents — Agent Submission Guide

## 🚀 Purpose

This repository is the central repository for all DigiDARA AI Agents.

Each team member is currently developing their own AI agent independently using tools such as:

- OpenAI Codex
- Claude Code
- GitHub Copilot
- Other AI coding agents

The goal is to bring all these independently developed agents into one centralized repository.

### Current Architecture

```text
                    DigiDARA AI Agents
                           │
                           │
              Central GitHub Repository
                           │
                           ▼
              DigiDARA-AI-Agents
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
   Agent Branch 1     Agent Branch 2     Agent Branch 3
        │                  │                  │
        ▼                  ▼                  ▼
   Voice Agent         RAG Agent        Sales Agent
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
                Central Integration Layer
                           │
                           ▼
                 ChatGPT-like Interface
```

The final objective is to provide a **single ChatGPT-like UI** where users can interact with the different DigiDARA AI agents from one platform.

---

# 1. Repository

Central repository:

**DigiDARA AI Agents**

```text
https://github.com/DigiDARATechnologies/DigiDARA-AI-Agents
```

You have already been given access to this repository.

You do **not** need to create a new GitHub repository for your agent.

---

# 2. What You Need to Do

If you already have your AI agent project working locally, your task is simple:

```text
Your Existing Agent
        ↓
Create a New Branch
        ↓
Copy/Commit Your Agent Code
        ↓
Push Branch to DigiDARA Repository
        ↓
Verify Branch on GitHub
        ↓
Inform the Team
```

### Important

**Do NOT push directly to `main`.**

Each developer must create a separate branch for their agent.

For example:

```text
main
│
├── agent/voice-agent
├── agent/rag-agent
├── agent/sales-agent
├── agent/support-agent
└── agent/document-agent
```

---

# 3. Branch Naming Convention

Please use:

```text
agent/<your-agent-name>
```

### Examples

```text
agent/voice-agent
agent/rag-agent
agent/sales-agent
agent/customer-support
agent/document-analyzer
agent/sql-agent
agent/whatsapp-agent
```

Use a short, meaningful name.

### ❌ Don't use

```text
mybranch
branch1
test
new
final
agent-final
test2
```

### ✅ Use

```text
agent/voice-agent
agent/rag-agent
agent/sql-agent
```

---

# 4. Before You Start

Make sure your existing agent is available locally.

For example:

```text
D:\Projects\MyVoiceAgent
```

or:

```text
C:\Users\YourName\Projects\RAG-Agent
```

Open this project in VS Code.

You can use:

```text
File → Open Folder
```

Then open the terminal.

```text
Terminal → New Terminal
```

---

# 5. Important Concept

Your existing agent does **not** have to be created from the central repository.

For example, you may currently have:

```text
My Local Agent
│
├── app.py
├── agent.py
├── tools/
├── requirements.txt
├── README.md
└── ...
```

You need to push this existing project into:

```text
DigiDARATechnologies/DigiDARA-AI-Agents
```

as your own branch.

---

# 6. Recommended Method — Let Your AI Agent Help

Since you are already using Codex / Claude Code / Copilot, you can ask your AI agent to perform the Git operations.

However, **do not immediately ask it to push everything**.

First ask it to inspect your project.

---

# 7. Step 1 — Ask AI Agent to Inspect Your Project

### Codex / Claude Code / Copilot Prompt

Copy this:

```text
I have an existing AI agent project in this directory.

I need to push this project to our company's central GitHub repository:

https://github.com/DigiDARATechnologies/DigiDARA-AI-Agents

I have permission to push to this repository.

Before making any changes, inspect my current project and Git state.

Please check:

1. Current directory
2. Whether Git is already initialized
3. Current branch
4. Git remote
5. Git status
6. Existing branches
7. Files currently present in the project

Do NOT commit anything.
Do NOT push anything.
Do NOT delete or modify anything.

Just inspect the repository and explain the current state.
```

Allow the AI agent to inspect the project.

---

# 8. Step 2 — Tell the AI Agent Your Branch Name

For example, suppose your agent is a:

```text
Voice Agent
```

Your branch should be:

```text
agent/voice-agent
```

Tell the AI:

```text
I want to push this agent as:

agent/voice-agent

The target repository is:

https://github.com/DigiDARATechnologies/DigiDARA-AI-Agents

Please create the branch from the appropriate base and switch to it.

Do not commit or push yet.
```

---

# 9. Step 3 — Check the Remote Repository

The AI agent should verify:

```bash
git remote -v
```

You want the remote to point to:

```text
https://github.com/DigiDARATechnologies/DigiDARA-AI-Agents
```

If your project already has another remote, such as:

```text
origin https://github.com/my-old-project/voice-agent.git
```

**DO NOT blindly replace it.**

Ask the AI agent:

```text
The current Git remote points to another repository.

I need to push this agent to:

https://github.com/DigiDARATechnologies/DigiDARA-AI-Agents

Please explain what needs to be changed before modifying the remote.
Do not push anything yet.
```

---

# 10. Step 4 — Create Your Agent Branch

The branch should be:

```text
agent/<agent-name>
```

For example:

```text
agent/voice-agent
```

The AI agent can execute:

```bash
git switch -c agent/voice-agent
```

Then verify:

```bash
git branch --show-current
```

Expected:

```text
agent/voice-agent
```

---

# 11. Step 5 — IMPORTANT: Check Secrets

Before pushing your agent, ask the AI agent to check for sensitive information.

Use this prompt:

```text
Before committing my agent, inspect the project for sensitive or unnecessary files.

Check for:

- .env
- API keys
- API tokens
- passwords
- credentials.json
- service account JSON files
- private keys
- SSH keys
- database passwords
- local configuration containing secrets
- large generated files
- virtual environments
- node_modules
- __pycache__

Do not delete anything.

Tell me which files should be added to .gitignore before committing.
```

### Never push these to GitHub:

```text
.env
credentials.json
service-account.json
*.pem
*.key
private keys
API tokens
passwords
```

---

# 12. Step 6 — Make Sure `.gitignore` Is Correct

Typical Python agent projects should have something similar to:

```gitignore
.env
.env.*
!.env.example

__pycache__/
*.pyc

.venv/
venv/
env/

node_modules/

.vscode/

*.log

.DS_Store
```

If your agent uses other technologies, your AI agent can recommend additional entries.

---

# 13. Step 7 — Review What Will Be Committed

Ask your AI agent:

```text
Now show me exactly what will be committed.

Run:

git status
git diff

Also provide a clean list of all files that will be included in the commit.

Do not commit yet.
```

Review the result.

You should see your actual agent files.

For example:

```text
agent/
├── app.py
├── agent.py
├── tools/
├── requirements.txt
├── README.md
└── config/
```

---

# 14. Step 8 — Stage the Agent

Once everything looks correct:

```bash
git add .
```

Then:

```bash
git status
```

Make sure sensitive files are NOT staged.

---

# 15. Step 9 — Commit

Use a meaningful commit message.

Example:

```bash
git commit -m "Add voice agent"
```

Other examples:

```text
Add RAG agent
Add SQL agent
Add customer support agent
Add document analysis agent
Add WhatsApp agent
```

You can ask your AI agent:

```text
The files have been reviewed and are ready.

Create a meaningful Git commit describing this AI agent.

Do not push yet.

After committing, show me:
- commit hash
- commit message
- current branch
- git status
```

---

# 16. Step 10 — Push Your Branch

Now push to the central repository.

For example:

```bash
git push -u origin agent/voice-agent
```

For another developer:

```bash
git push -u origin agent/rag-agent
```

Another:

```bash
git push -u origin agent/sql-agent
```

---

# 17. Recommended Final AI Prompt

If everything has been reviewed and committed, give the AI agent:

```text
The agent code has been reviewed and committed.

Now I need to push my branch to the central DigiDARA repository.

Repository:

https://github.com/DigiDARATechnologies/DigiDARA-AI-Agents

My branch:

agent/<agent-name>

Before pushing, verify:

1. Current branch is agent/<agent-name>
2. Remote points to DigiDARATechnologies/DigiDARA-AI-Agents
3. Latest commit is correct
4. There are no unexpected uncommitted changes
5. We are NOT on main
6. No secrets are being pushed

Then push:

git push -u origin agent/<agent-name>

Do NOT force push.
Do NOT push to main.
Do NOT delete any branches.

After pushing, verify that the remote branch exists.
```

---

# 18. Verify on GitHub

Open:

```text
https://github.com/DigiDARATechnologies/DigiDARA-AI-Agents
```

Go to:

```text
Branches
```

You should see your branch.

For example:

```text
main

agent/voice-agent
```

Another team member might have:

```text
agent/rag-agent
```

Another:

```text
agent/sql-agent
```

---

# 19. What the Final Repository Will Look Like

Eventually:

```text
DigiDARA-AI-Agents
│
├── main
│
├── agent/voice-agent
│
├── agent/rag-agent
│
├── agent/sql-agent
│
├── agent/customer-support
│
├── agent/document-analyzer
│
└── agent/sales-agent
```

Each branch represents an independently developed AI agent.

---

# 20. Important — Don't Merge Your Branch Yet

For now, your responsibility is:

```text
Develop Agent
      ↓
Create Agent Branch
      ↓
Push Agent Branch
      ↓
Verify Branch
      ↓
Inform Team
```

Do **not** merge your branch into `main` unless the project lead asks you to.

The integration team will review the different agents and decide how they should be structured for the final application.

---

# 21. Final Integration Goal

The purpose of collecting all these agents is **not simply to store them in GitHub**.

The bigger goal is to build a common AI platform.

Eventually:

```text
                         DigiDARA AI Platform
                                  │
                                  ▼
                       ┌─────────────────────┐
                       │  ChatGPT-like UI    │
                       │                     │
                       │  Chat / History     │
                       │  Agent Selection    │
                       │  File Upload        │
                       │  Tool Execution     │
                       └──────────┬──────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
              Voice Agent     RAG Agent     SQL Agent
                    │             │             │
                    ▼             ▼             ▼
              Voice Tools     RAG Tools     DB Tools
                    │             │             │
                    └─────────────┼─────────────┘
                                  ▼
                         Common Agent Runtime
                                  │
                                  ▼
                         DigiDARA Backend
```

The GitHub branches are therefore the **first step toward integrating all independently developed agents into one unified platform**.

---

# 22. What We Need From Each Team Member

Each developer should provide:

### 1. Agent Branch

Example:

```text
agent/voice-agent
```

### 2. Agent Name

Example:

```text
DigiDARA Voice Agent
```

### 3. Short Description

Example:

```text
AI voice agent capable of handling inbound/outbound calls and
performing automated conversations.
```

### 4. How to Run

Example:

```bash
pip install -r requirements.txt

python app.py
```

### 5. Required Environment Variables

Create:

```text
.env.example
```

Example:

```env
OPENAI_API_KEY=
DATABASE_URL=
```

**Do not put actual API keys inside `.env.example`.**

### 6. Agent Entry Point

Tell us which file starts the agent:

```text
app.py
main.py
server.py
```

or whatever is applicable.

### 7. API / Integration Information

If the agent exposes APIs, document:

```text
POST /chat
POST /execute
POST /upload
GET /health
```

etc.

---

# 23. Minimum README Required Inside Your Agent

Each agent should ideally contain its own:

```text
README.md
```

with:

```text
# Agent Name

## Description

What does this agent do?

## Features

- Feature 1
- Feature 2
- Feature 3

## Technologies

- Python
- LangGraph
- OpenAI
- Qdrant
- etc.

## Installation

How to install dependencies.

## Environment Variables

What environment variables are required.

## Running

How to start the agent.

## API Endpoints

If applicable.

## Architecture

Brief explanation of how the agent works.

## Tools

What tools does the agent use?

## Input

What does the agent expect?

## Output

What does the agent return?

## Example

Example request and response.
```

This will make the later integration process much easier.

---

# 24. ⚠️ Important Rules

### DO

✅ Use your own branch

```text
agent/<agent-name>
```

✅ Push your existing agent

✅ Include `requirements.txt` / `pyproject.toml`

✅ Include `.env.example`

✅ Include a README

✅ Document how to run your agent

✅ Document required APIs and tools

✅ Check for secrets before pushing

---

### DON'T

❌ Don't push directly to `main`

❌ Don't force push

❌ Don't delete other developers' branches

❌ Don't upload `.env`

❌ Don't upload API keys

❌ Don't upload passwords

❌ Don't upload credentials

❌ Don't upload virtual environments

❌ Don't overwrite another developer's branch

---

# 25. Quick Version

If you already understand Git, the complete process is simply:

```bash
# Go to your existing agent
cd /path/to/my-agent

# Check Git
git status

# Connect to central repository if required
git remote -v

# Create your branch
git switch -c agent/my-agent

# Review files
git status
git diff

# Stage
git add .

# Review staged files
git status

# Commit
git commit -m "Add my agent"

# Push
git push -u origin agent/my-agent
```

Then open the GitHub repository and verify your branch.

---

# 26. Final Message to the Team

Once you have successfully pushed your agent, send the team:

```text
Agent pushed successfully.

Branch:
agent/<agent-name>

Repository:
DigiDARA-AI-Agents

The agent code, requirements, README, and configuration documentation have been added to the branch.

Please review the branch when required.
```

---

# 🎯 Final Goal

Every developer's responsibility:

```text
Your Agent
    ↓
Your Branch
    ↓
Central DigiDARA Repository
    ↓
Review & Standardization
    ↓
Agent Integration
    ↓
Common Agent Runtime
    ↓
ChatGPT-like DigiDARA UI
    ↓
Multiple AI Agents from One Platform
```

**Your job is to push your working agent as a clean, documented branch.**

**The integration team will handle bringing the agents together into the final DigiDARA AI platform.**