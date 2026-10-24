"""Registry CRUD + the health filter the orchestrator relies on.

Non-negotiable rule (see architecture brief): no agent name is ever
hardcoded anywhere in the orchestrator. This module is the *only* place that
touches the agent_registry table — the graph and routes only ever call
`list_healthy()` / `register()` / etc., never raw SQL.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app import config
from app.db import get_session
from app.models import AgentRegistry
from app.schemas import AgentRegisterRequest

logger = logging.getLogger("orchestrator.registry")


def register(payload: AgentRegisterRequest) -> None:
    """Upsert by (agent_name, version). A re-register (e.g. on every agent
    boot) is treated the same as a heartbeat — it refreshes last_heartbeat
    and flips status back to "healthy" even if it had been marked dead."""
    session = get_session()
    try:
        existing = session.get(AgentRegistry, (payload.agent_name, payload.version))
        now = datetime.utcnow()
        if existing:
            existing.endpoint = payload.endpoint
            existing.description = payload.description
            existing.input_schema = payload.input_schema
            existing.output_schema = payload.output_schema
            existing.owner = payload.owner
            existing.plan_tier = payload.plan_tier
            existing.status = "healthy"
            existing.last_heartbeat = now
        else:
            session.add(
                AgentRegistry(
                    agent_name=payload.agent_name,
                    version=payload.version,
                    endpoint=payload.endpoint,
                    description=payload.description,
                    input_schema=payload.input_schema,
                    output_schema=payload.output_schema,
                    owner=payload.owner,
                    plan_tier=payload.plan_tier,
                    status="healthy",
                    last_heartbeat=now,
                )
            )
        try:
            session.commit()
        except Exception:
            # Every agent runs multiple worker processes that each try to
            # register on boot -- two can both see "no existing row" and
            # both attempt an insert, so the loser hits a primary-key
            # collision here. The winner already produced the correct end
            # state, so just retry this one as an update instead of
            # crashing the request.
            session.rollback()
            existing = session.get(AgentRegistry, (payload.agent_name, payload.version))
            if existing is None:
                raise
            existing.endpoint = payload.endpoint
            existing.description = payload.description
            existing.input_schema = payload.input_schema
            existing.output_schema = payload.output_schema
            existing.owner = payload.owner
            existing.plan_tier = payload.plan_tier
            existing.status = "healthy"
            existing.last_heartbeat = now
            session.commit()
        logger.info(
            "registered agent_name=%s version=%s endpoint=%s", payload.agent_name, payload.version, payload.endpoint
        )
    finally:
        session.close()


def heartbeat(agent_name: str, version: str, endpoint: str | None = None) -> bool:
    session = get_session()
    try:
        row = session.get(AgentRegistry, (agent_name, version))
        if row is None:
            return False
        row.last_heartbeat = datetime.utcnow()
        row.status = "healthy"
        # register() only runs once at process boot -- a container that's
        # been running since before its AGENT_PUBLIC_URL was corrected would
        # otherwise stay stuck on the stale endpoint until manually
        # restarted. Resyncing here self-heals that on the next heartbeat.
        if endpoint and endpoint != row.endpoint:
            logger.info(
                "heartbeat resynced stale endpoint for agent_name=%s version=%s old=%s new=%s",
                agent_name, version, row.endpoint, endpoint,
            )
            row.endpoint = endpoint
        session.commit()
        return True
    finally:
        session.close()


def mark_unhealthy(agent_name: str, version: str) -> bool:
    """Explicit self-reported shutdown/failure — lets an agent take itself
    out of rotation immediately instead of waiting for the heartbeat TTL."""
    session = get_session()
    try:
        row = session.get(AgentRegistry, (agent_name, version))
        if row is None:
            return False
        row.status = "unhealthy"
        session.commit()
        return True
    finally:
        session.close()


def deregister(agent_name: str, version: str) -> bool:
    """Takes the agent out of rotation. The row is kept (status
    "deregistered") rather than deleted: an agent runs several gunicorn
    workers and each deregisters when it exits, so one worker restarting used
    to delete the registration while its siblings were still serving, and
    every learner got "not registered" until the next heartbeat (up to 30 s).
    The next heartbeat from any live worker marks it healthy again."""
    session = get_session()
    try:
        row = session.get(AgentRegistry, (agent_name, version))
        if row is None or row.status == "deregistered":
            return False
        row.status = "deregistered"
        session.commit()
        return True
    finally:
        session.close()


def list_all() -> list[AgentRegistry]:
    session = get_session()
    try:
        return session.query(AgentRegistry).order_by(AgentRegistry.agent_name).all()
    finally:
        session.close()


def list_healthy() -> list[AgentRegistry]:
    """The orchestrator's one and only window into "what agents exist right
    now". An agent must be marked healthy AND have heartbeated within the TTL
    — a crashed agent that never got the chance to deregister falls out of
    this list on its own once its heartbeat goes stale."""
    session = get_session()
    try:
        cutoff = datetime.utcnow() - timedelta(seconds=config.HEARTBEAT_TTL_SECONDS)
        return (
            session.query(AgentRegistry)
            .filter(AgentRegistry.status == "healthy")
            .filter(AgentRegistry.last_heartbeat >= cutoff)
            .order_by(AgentRegistry.agent_name)
            .all()
        )
    finally:
        session.close()


# How long after its last heartbeat an agent is still tried when it is not
# currently "healthy" (a late heartbeat, a worker that just restarted).
TRAFFIC_GRACE_SECONDS = 600


def resolve_for_traffic(agent_name: str) -> AgentRegistry | None:
    """Where to send a learner's request: the healthy agent, or else the one
    that checked in most recently within TRAFFIC_GRACE_SECONDS. A heartbeat
    that is a few seconds late (the platform briefly busy, a worker
    restarting) no longer turns every click into "agent unavailable"; if the
    agent really is down, the call itself fails with "could not be reached"."""
    agent = resolve_healthy(agent_name)
    if agent is not None:
        return agent
    session = get_session()
    try:
        cutoff = datetime.utcnow() - timedelta(seconds=TRAFFIC_GRACE_SECONDS)
        agent = (
            session.query(AgentRegistry)
            .filter(AgentRegistry.agent_name == agent_name)
            # Not an agent that reported itself failing (mark_unhealthy).
            .filter(AgentRegistry.status.in_(("healthy", "deregistered")))
            .filter(AgentRegistry.last_heartbeat >= cutoff)
            .order_by(AgentRegistry.last_heartbeat.desc(), AgentRegistry.version.desc())
            .first()
        )
    finally:
        session.close()
    if agent is not None:
        logger.warning(
            "routing to %s although its heartbeat is late (status=%s last_heartbeat=%s)",
            agent_name, agent.status, agent.last_heartbeat,
        )
    return agent


def resolve_healthy(agent_name: str) -> AgentRegistry | None:
    """Resolve the freshest healthy version of an agent for gateway forwarding."""
    session = get_session()
    try:
        cutoff = datetime.utcnow() - timedelta(seconds=config.HEARTBEAT_TTL_SECONDS)
        return (
            session.query(AgentRegistry)
            .filter(AgentRegistry.agent_name == agent_name)
            .filter(AgentRegistry.status == "healthy")
            .filter(AgentRegistry.last_heartbeat >= cutoff)
            # version as a tiebreak: last_heartbeat now has microsecond
            # precision (see models.py), but two versions could still
            # heartbeat at the exact same instant -- an unordered tie would
            # otherwise pick whichever row MySQL happens to scan first.
            .order_by(AgentRegistry.last_heartbeat.desc(), AgentRegistry.version.desc())
            .first()
        )
    finally:
        session.close()
