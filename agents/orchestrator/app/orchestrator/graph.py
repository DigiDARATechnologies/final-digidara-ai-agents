"""The orchestrator's LangGraph supervisor.

Four nodes, one conditional edge:

    load_registry --> route --[tool chosen]--> invoke_agent --> summarize --> END
                          \\--[no tool / general chat]--------------------> END

`load_registry` is what makes this "runtime service discovery" instead of a
hardcoded router: it reads whichever agents are registered and heartbeating
*at this exact moment* and builds the tool list from that. No agent name is
hardcoded anywhere in this file — adding agent #101 requires zero changes
here, only a new row in the registry (see agents/agent_template).

Stateless per turn on purpose: the registry can change between any two user
messages (an agent could restart, or agent #101 could come online mid
conversation), so re-reading it every turn is a feature, not a wasted call.
`thread_id` is accepted end-to-end purely so the frontend has a stable id to
keep local chat history; the graph itself carries no memory of past turns.
"""
from __future__ import annotations

import logging
from typing import Any, TypedDict

import httpx
from langgraph.graph import END, StateGraph

from app import config
from app.llm.client import call_text, call_with_tools
from app.orchestrator import prompts
from app.orchestrator.tools import build_tools, endpoint_for
from app.registry import service as registry_service

logger = logging.getLogger("orchestrator.graph")


class OrchestratorState(TypedDict, total=False):
    message: str
    history: list[dict[str, str]]
    tools: list[dict[str, Any]]
    agents: list[Any]  # AgentRegistry rows for this turn, kept only to resolve tool_name -> endpoint
    tool_name: str | None
    tool_args: dict[str, Any]
    agent_result: Any
    agent_error: str | None
    agent_used: str | None
    reply: str


# --- Node 1: load whatever agents are live right now (deterministic) -------

def load_registry_node(state: OrchestratorState) -> dict:
    agents = registry_service.list_healthy()
    logger.info("registry snapshot: %d healthy agent(s)", len(agents))
    return {"tools": build_tools(agents), "agents": agents}


# --- Node 2: LLM decides whether a tool fits, or answers directly ----------

def route_node(state: OrchestratorState) -> dict:
    tools = state.get("tools") or []
    result = call_with_tools(
        system=prompts.router_system_prompt(has_tools=bool(tools)),
        user=state["message"],
        tools=tools,
        history=state.get("history"),
    )
    if "tool_name" in result:
        return {"tool_name": result["tool_name"], "tool_args": result.get("tool_args", {})}
    return {"tool_name": None, "reply": result.get("text", "")}


def _route_after_selection(state: OrchestratorState) -> str:
    return "invoke_agent" if state.get("tool_name") else "done"


# --- Node 3: call the chosen agent's own endpoint (deterministic) ----------

def invoke_agent_node(state: OrchestratorState) -> dict:
    tool_name = state["tool_name"]
    endpoint = endpoint_for(state.get("agents") or [], tool_name)
    if not endpoint:
        # Registry changed between load_registry and here (agent deregistered
        # mid-turn) — surface it as a normal chat reply, not a 500.
        return {"agent_error": "this agent just went offline", "agent_used": tool_name}

    try:
        resp = httpx.post(endpoint, json=state.get("tool_args") or {}, timeout=config.AGENT_CALL_TIMEOUT_SECONDS)
        resp.raise_for_status()
        return {"agent_result": resp.json(), "agent_used": tool_name}
    except Exception as exc:  # noqa: BLE001 — any transport/HTTP failure becomes a clean chat reply, not a crash
        logger.exception("agent call failed: name=%s endpoint=%s", tool_name, endpoint)
        return {"agent_error": str(exc), "agent_used": tool_name}


# --- Node 4: turn the raw agent result into a human-readable reply (LLM) ---

def summarize_node(state: OrchestratorState) -> dict:
    agent_used = state.get("agent_used") or "the agent"
    if state.get("agent_error"):
        return {"reply": prompts.error_reply(agent_used, state["agent_error"])}

    reply = call_text(
        system=prompts.summarize_system_prompt(agent_used),
        user=f"Original user message: {state['message']}\n\nAgent result:\n{state.get('agent_result')}",
    )
    return {"reply": reply}


def route_message(message: str, history: list[dict[str, str]] | None = None) -> dict:
    """load_registry + route only — no agent invocation, no summarize. Used
    by POST /chat/route for handoff-style UIs that run the matched agent's
    own dedicated multi-turn flow client-side instead of a single stateless
    tool call. Reuses load_registry_node/route_node unmodified; a second
    compiled StateGraph would be pure overhead for two sequential calls."""
    state: OrchestratorState = {"message": message, "history": history or []}
    state.update(load_registry_node(state))
    state.update(route_node(state))
    return {"agent_name": state.get("tool_name"), "reply": state.get("reply")}


def build_orchestrator_graph():
    graph = StateGraph(OrchestratorState)

    graph.add_node("load_registry", load_registry_node)
    graph.add_node("route", route_node)
    graph.add_node("invoke_agent", invoke_agent_node)
    graph.add_node("summarize", summarize_node)

    graph.set_entry_point("load_registry")
    graph.add_edge("load_registry", "route")
    graph.add_conditional_edges(
        "route",
        _route_after_selection,
        {"invoke_agent": "invoke_agent", "done": END},
    )
    graph.add_edge("invoke_agent", "summarize")
    graph.add_edge("summarize", END)

    return graph.compile()  # no checkpointer — each turn is independent, see module docstring


# Single shared compiled graph for the app's lifetime.
orchestrator_graph = build_orchestrator_graph()
