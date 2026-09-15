from app.logging_config import setup_logging

setup_logging()  # must run before importing modules below, so their loggers pick it up

import os  # noqa: E402

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from slowapi.middleware import SlowAPIMiddleware  # noqa: E402

from app.auth.routes import router as auth_router  # noqa: E402
from app.auth import service as auth_service  # noqa: E402
from app.db import init_db  # noqa: E402
from app.gateway.routes import router as gateway_router  # noqa: E402
from app.orchestrator.routes import router as chat_router  # noqa: E402
from app.rate_limit import limiter  # noqa: E402
from app.registry.routes import router as registry_router  # noqa: E402
from app.billing.routes import router as billing_router  # noqa: E402
from app.chat_history.routes import router as chat_history_router  # noqa: E402

app = FastAPI(title="DigiDARA Orchestrator", version="1.0.0")

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    response = JSONResponse({"detail": "Too many requests. Please slow down and try again shortly."}, status_code=429)
    # Every limit configured in this app is a "N per minute" window, so 60s
    # is always a correct (if occasionally conservative) worst case.
    response.headers["Retry-After"] = "60"
    return response


ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(registry_router)
app.include_router(chat_router)
app.include_router(gateway_router)
app.include_router(billing_router)
app.include_router(chat_history_router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    auth_service.seed_admin_from_env()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
