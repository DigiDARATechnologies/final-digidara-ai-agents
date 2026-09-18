from typing import Any

from pydantic import BaseModel, Field


class AgentRegisterRequest(BaseModel):
    agent_name: str = Field(min_length=1)
    version: str = "v1.0.0"
    endpoint: str = Field(min_length=1)
    description: str = Field(min_length=1)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] = Field(default_factory=dict)
    owner: str | None = None
    plan_tier: str = "free"


class HeartbeatRequest(BaseModel):
    agent_name: str
    version: str
    # Optional so older agent clients that don't send it yet keep working
    # unchanged. When present, resyncs the registry's stored endpoint on
    # every heartbeat (every HEARTBEAT_INTERVAL_SECONDS) instead of only at
    # process boot -- a long-lived agent process whose AGENT_PUBLIC_URL was
    # corrected after it last started would otherwise stay registered under
    # its stale endpoint indefinitely, since register() only runs once at
    # startup and a plain heartbeat previously never touched `endpoint`.
    endpoint: str | None = None


class AgentOut(BaseModel):
    agent_name: str
    version: str
    endpoint: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    owner: str | None
    plan_tier: str
    status: str
    last_heartbeat: str | None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    thread_id: str | None = None


class ChatResponse(BaseModel):
    thread_id: str
    reply: str
    agent_used: str | None = None


class RouteTurn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class RouteRequest(BaseModel):
    message: str = Field(min_length=1)
    # Prior turns of *this* chat, oldest first, NOT including `message` itself
    # — see orchestrator/graph.py's route_node for why this exists: routing
    # used to see only the single latest message, so a vague opener followed
    # by several turns of the user adding detail never accumulated enough
    # signal to route, and just kept re-asking the same clarifying question
    # forever.
    history: list[RouteTurn] = Field(default_factory=list)


class RouteResponse(BaseModel):
    agent_name: str | None = None
    reply: str | None = None
