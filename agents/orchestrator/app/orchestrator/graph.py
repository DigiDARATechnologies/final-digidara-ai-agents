"""How the general chat picks an agent.

    load_registry --> route --[tool chosen]--> the browser opens that agent's own flow
                          \--[no tool / general chat]--> the reply

This only decides. It never calls an agent itself: an agent is reached through
the gateway, which signs the call for the verified learner and checks it.

`load_registry` is what makes this "runtime service discovery" instead of a
hardcoded router: it reads whichever agents are registered and heartbeating
*at this exact moment* and builds the tool list from that. No agent name is
hardcoded anywhere in this file — adding agent #101 requires zero changes
here, only a new row in the registry (see agents/agent_template).

Stateless per turn on purpose: the registry can change between any two user
messages (an agent could restart, or agent #101 could come online mid
conversation), so re-reading it every turn is a feature, not a wasted call.
"""
from __future__ import annotations

import logging
from typing import Any, TypedDict

from app.llm.client import call_with_tools, stream_with_tools
from app.orchestrator import guard, prompts
from app.orchestrator.tools import build_tools
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
    # Filled with the tokens Boss's own model calls used, charged as points.
    usage: dict[str, int]


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
        usage=state.get("usage"),
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


def route_message(message: str, history: list[dict[str, str]] | None = None, learner_context: dict | None = None,
                  usage: dict[str, int] | None = None) -> dict:
    """load_registry + route only — no agent invocation, no summarize. Used
    by POST /chat/route for handoff-style UIs that run the matched agent's
    own dedicated multi-turn flow client-side instead of a single stateless
    tool call. Reuses load_registry_node/route_node unmodified; a second
    compiled StateGraph would be pure overhead for two sequential calls."""
    state: OrchestratorState = {"message": message, "history": history or [], "learner_context": learner_context}
    if usage is not None:
        state["usage"] = usage
    state.update(load_registry_node(state))
    state.update(route_node(state))
    return {"agent_name": state.get("tool_name"), "reply": state.get("reply")}


def route_message_stream(
    message: str, history: list[dict[str, str]] | None = None, learner_context: dict | None = None, voice: bool = False,
    usage: dict[str, int] | None = None,
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
    for kind, value in stream_with_tools(system, message, tools, guard.safe_history(history), max_tokens=260 if voice else 700,
                                         usage=usage):
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
