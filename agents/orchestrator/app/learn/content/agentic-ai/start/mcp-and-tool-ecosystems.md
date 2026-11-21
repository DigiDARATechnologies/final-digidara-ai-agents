---
title: MCP and the tool ecosystem
summary: Understand the Model Context Protocol, the open standard for connecting AI applications to tools and data, and see what a small MCP server looks like.
takeaways:
- MCP is a common standard so any AI app can use any tool server, like USB for AI tools
- An MCP server offers tools, resources and prompts; an AI app connects as the client
- Connect only servers you trust, and give them the least access they need
---
## The problem MCP solves

Without a standard, every AI app needs custom code for every tool: one way to read Google Drive, another for GitHub, another for your database. With many apps and many tools, that is a large pile of one-off connections.

The **Model Context Protocol (MCP)**, an open standard introduced by Anthropic and now widely adopted, defines **one common way** for AI applications to talk to tools and data. Build a tool server **once**, and any MCP-capable app can use it.

| Without MCP | With MCP |
| --- | --- |
| each app builds its own integration for each tool | each tool is built once as an MCP server |
| changing the tool means changing every app | apps keep working |

## The parts

| Part | Role | Example |
| --- | --- | --- |
| **MCP host** | the AI application the user works in | Claude Desktop, an IDE assistant, your own agent |
| **MCP client** | the connector inside the host that talks to one server | built into the host |
| **MCP server** | a small program that offers capabilities | "file search", "database", "calendar" |

A server can offer three kinds of capability:

| Capability | Meaning | Example |
| --- | --- | --- |
| **Tools** | actions the model can request | `search_notes(query)`, `send_email(...)` |
| **Resources** | data the app can read | a file, a database row, a document |
| **Prompts** | reusable prompt templates | "summarise this document" |

Servers run **locally** (talking over standard input and output) or **remotely** (over HTTP).

## A tiny MCP server in Python

With the official Python SDK (`pip install mcp`), a tool server is a few lines:

```py
# study_server.py
from datetime import date
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("study-tools")

EXAM_DATES = {"maths": "2026-12-10", "physics": "2026-12-14"}

@mcp.tool()
def get_exam_date(subject: str) -> str:
    """Look up the exam date for a subject, as YYYY-MM-DD."""
    return EXAM_DATES.get(subject.lower(), "unknown subject")

@mcp.tool()
def days_until(target: str) -> int:
    """Number of days from today until a date given as YYYY-MM-DD."""
    return (date.fromisoformat(target) - date.today()).days

if __name__ == "__main__":
    mcp.run()                 # starts the server (standard input and output by default)
```

The function name, type hints and docstring become the tool's **name, input schema and description** automatically. This is the same information we wrote by hand in the tool-calling lesson.

## Connecting it to an app

A host such as Claude Desktop is told where the server is in a configuration file:

```py
{
  "mcpServers": {
    "study-tools": {
      "command": "python",
      "args": ["study_server.py"]
    }
  }
}
```

After restarting the app, the model can see `get_exam_date` and `days_until` and call them when a question needs them. The app shows the user which tool is being called and usually asks for permission.

## Popular servers you can use

| Server | What it gives an AI app |
| --- | --- |
| **filesystem** | read and search local files |
| **GitHub** | issues, pull requests, repositories |
| **database servers** (PostgreSQL, SQLite) | run read-only queries |
| **web fetch and search** | read pages and find information |
| **Slack, Google Drive, calendars** | team and personal data |

Search the official MCP servers list and the SDK documentation for the current choices, since the ecosystem grows quickly.

## Security: treat MCP servers like software you install

| Risk | What to do |
| --- | --- |
| a **malicious or buggy server** | install only from sources you trust; read what it does |
| **too much access** | give each server the minimum: a specific folder, a read-only database user |
| **prompt injection through tool results** | text a tool returns (a web page, an email) can contain instructions; treat it as untrusted data |
| **secrets** | keep keys in environment variables, never in prompts or config you commit |
| **destructive actions** | require human approval for deletes, payments and sending messages |

:::warning
A tool server can read your files and use your accounts. Connecting an unknown MCP server is like running an unknown program. Review it, limit its access, and keep approval prompts switched on.
:::

## Why this matters for you

Whether or not you use MCP specifically, the ideas will stay: tools described with schemas, servers separate from the model, permissions and approvals. Building one small MCP server for your own notes or college data is a strong, current portfolio project.

:::interview
**Interviewers often ask:** "What is MCP?" The Model Context Protocol is an open standard that lets AI applications connect to external tools and data through a common interface. A server exposes tools, resources and prompts; a host application connects as a client, so a tool is built once and works across applications.
:::
