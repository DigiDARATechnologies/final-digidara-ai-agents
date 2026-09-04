"""Converts live registry rows into OpenAI-style function-calling tool specs.
This is the dynamic-not-hardcoded translation layer the brief calls for:
`tools = [to_tool_spec(a) for a in registry.list_healthy()]`."""
from __future__ import annotations

from typing import Any

from app.models import AgentRegistry


def to_tool_spec(agent: AgentRegistry) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": agent.agent_name,
            "description": agent.description,
            "parameters": agent.input_schema or {"type": "object", "properties": {}},
        },
    }


def build_tools(agents: list[AgentRegistry]) -> list[dict[str, Any]]:
    return [to_tool_spec(a) for a in agents]


def endpoint_for(agents: list[AgentRegistry], agent_name: str) -> str | None:
    for a in agents:
        if a.agent_name == agent_name:
            return a.endpoint
    return None
