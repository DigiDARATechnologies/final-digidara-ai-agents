"""The general/router chat's ONLY job is connecting a user to the right
registered agent -- it must never answer a general-knowledge question
itself, even when no agent matches. See app/orchestrator/prompts.py."""
from unittest.mock import Mock

from app.llm import client as llm_client
from app.orchestrator import graph, prompts


def test_router_prompt_forbids_general_knowledge_answers_with_tools():
    prompt = prompts.router_system_prompt(has_tools=True)
    assert "not a general-purpose chatbot" in prompt
    assert "general-knowledge question" in prompt
    assert "do NOT answer it" in prompt


def test_router_prompt_forbids_general_knowledge_answers_without_tools():
    prompt = prompts.router_system_prompt(has_tools=False)
    assert "never answer a general-knowledge or trivia question" in prompt
    assert "nothing to route to right now" in prompt


def test_router_prompt_still_allows_answering_about_the_platform_itself():
    prompt = prompts.router_system_prompt(has_tools=True)
    assert "about THIS platform or its agents" in prompt


class _FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, name, arguments):
        self.function = _FakeFunction(name, arguments)


class _FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _FakeResponse:
    def __init__(self, message):
        self.choices = [type("Choice", (), {"message": message})()]


def test_route_node_calls_a_matching_agent_tool(monkeypatch):
    monkeypatch.setattr(
        llm_client.litellm, "completion",
        Mock(return_value=_FakeResponse(_FakeMessage(content=None, tool_calls=[_FakeToolCall("capstone_project_agent", '{"question": "hi"}')]))),
    )
    result = graph.route_node({"message": "I need help with my capstone project", "tools": [{"type": "function", "function": {"name": "capstone_project_agent", "description": "..."}}]})
    assert result["tool_name"] == "capstone_project_agent"


def test_route_node_returns_direct_reply_when_no_tool_matches(monkeypatch):
    monkeypatch.setattr(
        llm_client.litellm, "completion",
        Mock(return_value=_FakeResponse(_FakeMessage(content="I connect you to DigiDARA's agents -- what are you trying to do?", tool_calls=None))),
    )
    result = graph.route_node({"message": "who is the prime minister of India", "tools": []})
    assert result["tool_name"] is None
    assert "DigiDARA" in result["reply"]
