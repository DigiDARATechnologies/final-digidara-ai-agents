from fastapi import APIRouter, Depends, HTTPException

from app.auth.service_auth import require_service_signature
from app.models import AgentRegistry
from app.registry import service
from app.schemas import AgentOut, AgentRegisterRequest, HeartbeatRequest

# Every route here is called by another backend service (an agent's own
# registration/heartbeat client), never by a browser — so all of them
# require the shared-secret HMAC signature, including the listing route:
# there is no admin-auth mechanism in this codebase to fall back to, and
# leaving agent endpoints/schemas world-readable is its own information
# disclosure.
router = APIRouter(prefix="/registry", tags=["registry"], dependencies=[Depends(require_service_signature)])


def _to_out(row: AgentRegistry) -> AgentOut:
    return AgentOut(
        agent_name=row.agent_name,
        version=row.version,
        endpoint=row.endpoint,
        description=row.description,
        input_schema=row.input_schema,
        output_schema=row.output_schema,
        owner=row.owner,
        plan_tier=row.plan_tier,
        status=row.status,
        last_heartbeat=row.last_heartbeat.isoformat() if row.last_heartbeat else None,
    )


@router.post("/register", status_code=201)
def register_agent(req: AgentRegisterRequest) -> dict:
    """Called by an agent's own startup hook — see agents/agent_template.
    Idempotent: calling it again (e.g. on every boot) just refreshes the
    registration, so redeploys of an unrelated agent never touch this row."""
    service.register(req)
    return {"ok": True}


@router.post("/heartbeat")
def heartbeat(req: HeartbeatRequest) -> dict:
    if not service.heartbeat(req.agent_name, req.version, req.endpoint):
        raise HTTPException(404, f"{req.agent_name}@{req.version} is not registered — register first.")
    return {"ok": True}


@router.delete("/deregister")
def deregister(agent_name: str, version: str) -> dict:
    if not service.deregister(agent_name, version):
        raise HTTPException(404, f"{agent_name}@{version} is not registered.")
    return {"ok": True}


@router.get("/agents", response_model=list[AgentOut])
def list_agents(healthy_only: bool = False) -> list[AgentOut]:
    rows = service.list_healthy() if healthy_only else service.list_all()
    return [_to_out(r) for r in rows]
