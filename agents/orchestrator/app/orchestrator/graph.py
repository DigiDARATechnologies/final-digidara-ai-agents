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

import json
import logging
from typing import Any, TypedDict

import httpx

from langgraph.graph import END, StateGraph

from app import config
from app.auth.agent_signing import sign_headers
from app.llm.client import call_text, call_with_tools, stream_with_tools
from app.orchestrator import guard, prompts
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
    # Phase 2: the learner's goal, skills and shared memory, for a personal answer.
    learner_context: dict[str, Any] | None


# --- Node 1: load whatever agents are live right now (deterministic) -------

def load_registry_node(state: OrchestratorState) -> dict:
    agents = registry_service.list_healthy()
    logger.info("registry snapshot: %d healthy agent(s)", len(agents))
    return {"tools": build_tools(agents), "agents": agents}


# --- Node 2: LLM decides whether a tool fits, or answers directly ----------

def route_node(state: OrchestratorState) -> dict:
    # An obvious injection attempt never reaches the model.
    if guard.looks_like_injection(state["message"]):
        logger.warning("general chat: blocked a prompt-injection attempt (%d chars)", len(state["message"]))
        return {"tool_name": None, "reply": guard.OFF_LIMITS_REPLY}
    tools = state.get("tools") or []
    system = prompts.router_system_prompt(has_tools=bool(tools))
    if state.get("learner_context"):
        system = f"{system}\n\n{prompts.learner_context_block(state['learner_context'])}"
    result = call_with_tools(
        system=system,
        user=state["message"],
        tools=tools,
        history=guard.safe_history(state.get("history")),
    )
    if "tool_name" in result:
        # Only an agent that is registered and live right now; a made-up or
        # stale name is treated as no match rather than handed to the app.
        if result["tool_name"] in {tool["function"]["name"] for tool in tools}:
            return {"tool_name": result["tool_name"], "tool_args": result.get("tool_args", {})}
        logger.warning("general chat: model chose an unknown agent %r", result["tool_name"])
        return {"tool_name": None, "reply": guard.OFF_LIMITS_REPLY}
    reply = result.get("text", "")
    if guard.leaks_instructions(reply):
        logger.warning("general chat: replaced a reply that leaked the instructions")
        reply = guard.OFF_LIMITS_REPLY
    return {"tool_name": None, "reply": reply}


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
        body = json.dumps(state.get("tool_args") or {}).encode()
        resp = httpx.post(
            endpoint,
            content=body,
            headers={"Content-Type": "application/json", **sign_headers(tool_name, "POST", endpoint, body)},
            timeout=config.AGENT_CALL_TIMEOUT_SECONDS,
        )
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


def route_message(message: str, history: list[dict[str, str]] | None = None, learner_context: dict | None = None) -> dict:
    """load_registry + route only — no agent invocation, no summarize. Used
    by POST /chat/route for handoff-style UIs that run the matched agent's
    own dedicated multi-turn flow client-side instead of a single stateless
    tool call. Reuses load_registry_node/route_node unmodified; a second
    compiled StateGraph would be pure overhead for two sequential calls."""
    state: OrchestratorState = {"message": message, "history": history or [], "learner_context": learner_context}
    state.update(load_registry_node(state))
    state.update(route_node(state))
    return {"agent_name": state.get("tool_name"), "reply": state.get("reply")}


def route_message_stream(
    message: str, history: list[dict[str, str]] | None = None, learner_context: dict | None = None, voice: bool = False,
):
    """route_message, streamed for the general chat: yields {"delta": text}
    while the answer is written, then one {"done": True, "agent_name", "reply"}.
    The instructions-leak guard still applies: text is held back by the
    canary's length, and a leak replaces the whole reply ({"replace": ...}).
    `voice`: the learner is talking to Boss, so the answer is kept to a few
    short spoken sentences (it is read aloud as it arrives)."""
    if guard.looks_like_injection(message):
        logger.warning("general chat: blocked a prompt-injection attempt (%d chars)", len(message))
        yield {"done": True, "agent_name": None, "reply": guard.OFF_LIMITS_REPLY}
        return
    state: OrchestratorState = {"message": message, "history": history or [], "learner_context": learner_context}
    state.update(load_registry_node(state))
    tools = state.get("tools") or []
    system = prompts.router_system_prompt(has_tools=bool(tools))
    if learner_context:
        system = f"{system}\n\n{prompts.learner_context_block(learner_context)}"
    if voice:
        system = f"{system}\n\n{prompts.VOICE_REPLY_RULES}"
    hold = len(guard.CANARY)
    text = ""
    sent = 0
    chosen: dict | None = None
    for kind, value in stream_with_tools(system, message, tools, guard.safe_history(history), max_tokens=260 if voice else 700):
        if kind == "tool":
            chosen = value
            continue
        text += value
        if guard.leaks_instructions(text):
            logger.warning("general chat: replaced a streamed reply that leaked the instructions")
            yield {"replace": guard.OFF_LIMITS_REPLY}
            yield {"done": True, "agent_name": None, "reply": guard.OFF_LIMITS_REPLY}
            return
        if len(text) - hold > sent:
            yield {"delta": text[sent:len(text) - hold]}
            sent = len(text) - hold
    if chosen and not text.strip():
        if chosen["tool_name"] in {tool["function"]["name"] for tool in tools}:
            yield {"done": True, "agent_name": chosen["tool_name"], "reply": None}
            return
        logger.warning("general chat: model chose an unknown agent %r", chosen["tool_name"])
        yield {"done": True, "agent_name": None, "reply": guard.OFF_LIMITS_REPLY}
        return
    if sent < len(text):
        yield {"delta": text[sent:]}
    yield {"done": True, "agent_name": None, "reply": text.strip()}


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
