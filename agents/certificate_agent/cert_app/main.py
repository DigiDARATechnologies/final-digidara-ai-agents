import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from cert_app.db.database import init_db
from cert_app.api import auth, exam, certificate, chat, invoke
from cert_app.integration.agent_signing import GatewaySignatureMiddleware
from cert_app.integration.registry_client import registry_client
from cert_app.config import get_settings

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[INFO] Starting AI Certification Agent...")
    init_db()
    os.makedirs(settings.CERTIFICATES_DIR, exist_ok=True)
    if os.environ.get("TESTING") != "True":
        await registry_client.start()
    yield
    if os.environ.get("TESTING") != "True":
        await registry_client.stop()
    logger.info("[SHUTDOWN] Shutting down AI Certification Agent")


app = FastAPI(
    title="AI Certification Agent",
    description="Advanced AI-powered certification exam & certificate system",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(GatewaySignatureMiddleware, agent_name="certificate_agent")

# Static files
app.mount("/static", StaticFiles(directory="cert_app/ui/static"), name="static")
app.mount("/cert/static", StaticFiles(directory="cert_app/ui/static"), name="cert_static")

# Strategy F Invoke Router (unauthenticated / CSRF-exempt)
app.include_router(invoke.router, tags=["Strategy F"])

# API Routers
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(exam.router, prefix="/api/exam", tags=["Exam"])
app.include_router(certificate.router, prefix="/api/certificate", tags=["Certificate"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])


from cert_app.services.auth_service import verify_token
from cert_app.api.auth import is_valid_handoff_code


# Frontend Pages
@app.get("/")
async def home(token: str = None, code: str = None, topic: str = None, mode: str = None, student: str = None):
    """
    Unified entry point - Serves exam.html ONLY if a valid single-use exchange
    code or cryptographically verified JWT token is provided.
    """
    logger.info(f"🔍 Home route called - code: {'YES' if code else 'NO'}, token: {'YES' if token else 'NO'}, topic: {topic or 'NO'}")

    if code:
        if is_valid_handoff_code(code):
            logger.info(f"✅ Valid single-use handoff exchange code provided — serving exam.html directly")
            return FileResponse("cert_app/ui/exam.html")
        else:
            logger.warning(f"❌ Invalid or expired handoff exchange code — falling through to login page")

    if token:
        payload = verify_token(token)
        if payload:
            logger.info(f"✅ Cryptographically verified JWT token for user {payload.get('sub')} — serving exam.html directly")
            return FileResponse("cert_app/ui/exam.html")
        else:
            logger.warning("❌ Invalid or unverified JWT token in URL — falling through to login page")

    logger.info("❌ No valid authentication or handoff code — serving login page (index.html)")
    return FileResponse("cert_app/ui/index.html")

@app.get("/dashboard")
async def dashboard():
    return FileResponse("cert_app/ui/dashboard.html")

@app.get("/exam")
async def exam_page():
    return FileResponse("cert_app/ui/exam.html")

@app.get("/result")
async def result_page():
    return FileResponse("cert_app/ui/result.html")

@app.get("/chat")
async def chat_page():
    return FileResponse("cert_app/ui/chat.html")