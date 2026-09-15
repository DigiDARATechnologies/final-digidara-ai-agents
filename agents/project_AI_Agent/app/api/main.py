from app.logging_config import setup_logging

setup_logging()  # must run before importing modules below, so their loggers pick it up

import os  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.api.routes import router  # noqa: E402
from app.db.database import init_db  # noqa: E402
from app.integration.registry_client import registry_client  # noqa: E402
from app.request_context import current_user_id  # noqa: E402

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    await registry_client.start()
    yield
    await registry_client.stop()


app = FastAPI(title="DigiDARA Capstone Project Agent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def bind_request_user(request, call_next):
    # Lets deep call sites (e.g. app/llm/client.py's usage logging) attribute
    # work to the caller without threading the header through every function.
    token = current_user_id.set(request.headers.get("x-digidara-user-id"))
    try:
        return await call_next(request)
    finally:
        current_user_id.reset(token)

app.include_router(router)

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
