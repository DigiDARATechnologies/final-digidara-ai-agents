from pathlib import Path
import time
import uuid
import click
from flask import Flask, jsonify, request, send_from_directory, g
from flask_cors import CORS
from sqlalchemy.exc import OperationalError
from .config import Config
from .extensions import db, migrate
from .utils.errors import APIError
from .utils.logging import configure_logging


def create_app(config_object=Config):
    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    app = Flask(__name__, static_folder=str(frontend_dist), static_url_path="")
    app.config.from_object(config_object)
    Config.validate(app)
    db.init_app(app)
    migrate.init_app(app, db, directory=str(Path(__file__).resolve().parents[1] / "migrations"))
    CORS(app, origins=[app.config["FRONTEND_ORIGIN"]], supports_credentials=False)
    configure_logging(app)

    from .models import load_models
    load_models()
    from .routes import register_blueprints
    register_blueprints(app)

    @app.cli.command("openai-check")
    @click.option("--full",is_flag=True,help="Also verify plain-text completion used by hints and recommendations.")
    def openai_check(full):
        """Verify structured OpenAI connectivity; --full also checks text generation."""
        from .services.ai_service import json_completion, text_completion
        if not app.config.get("OPENAI_API_KEY"):
            raise click.ClickException("OPENAI_API_KEY is not configured in .env")
        try:
            result=json_completion(
                "Return JSON only.",
                'Return exactly {"status":"ok"}.',
                0,
            )
            if result is None:
                raise RuntimeError("OpenAI returned no response")
            payload,usage=result
            message=f"OpenAI JSON connectivity OK. model={usage.get('model')} tokens={usage.get('total_tokens',0)} payload={payload}"
            if full:
                text_result=text_completion("Reply with only OK.","Return OK.",maximum_tokens=8)
                if text_result is None or not text_result[0].strip():
                    raise RuntimeError("OpenAI returned no plain-text response")
                text, text_usage=text_result
                message+=f"\nOpenAI text connectivity OK. model={text_usage.get('model')} tokens={text_usage.get('total_tokens',0)} response={text.strip()[:40]}"
            click.echo(message)
        except Exception as exc:
            raise click.ClickException(f"OpenAI connectivity failed: {type(exc).__name__}: {exc}") from exc

    @app.before_request
    def request_context():
        request.environ["aptitude.request_id"] = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:80]
        request.environ["aptitude.started_at"] = time.perf_counter()

    @app.after_request
    def secure_headers(response):
        duration_ms=(time.perf_counter()-request.environ.get("aptitude.started_at",time.perf_counter()))*1000
        response.headers["X-Request-ID"] = request.environ.get("aptitude.request_id", "")
        response.headers["X-Tokens-Used"] = str(g.get("tokens_used_this_request", 0))
        response.headers["Server-Timing"] = f"app;dur={duration_ms:.2f}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; connect-src 'self'; img-src 'self' data: blob:; script-src 'self'"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            app.logger.info("HTTP method=%s path=%s status=%s duration_ms=%.2f request_id=%s",request.method,request.path,response.status_code,duration_ms,request.environ.get("aptitude.request_id",""))
        return response

    @app.errorhandler(APIError)
    def api_error(error):
        payload = {"error": error.message, "code": error.code, "request_id": request.environ.get("aptitude.request_id")}
        if error.details: payload["details"] = error.details
        return jsonify(payload), error.status

    @app.errorhandler(OperationalError)
    def database_unavailable(error):
        db.session.rollback()
        app.logger.error("MySQL connection failed: %s", type(getattr(error, "orig", error)).__name__)
        return jsonify(error="MySQL is unavailable or rejected the configured account. Check DATABASE_URL and MySQL grants.", code="database_unavailable", request_id=request.environ.get("aptitude.request_id")), 503

    @app.errorhandler(404)
    def not_found(_):
        if request.path.startswith("/api/"):
            return jsonify(error="Not found", code="not_found"), 404
        if frontend_dist.joinpath("index.html").exists():
            return send_from_directory(frontend_dist, "index.html")
        return jsonify(error="Frontend build not found. Run npm run build in frontend."), 404

    @app.errorhandler(500)
    def internal(error):
        db.session.rollback()
        app.logger.exception("Unhandled request error", exc_info=error)
        return jsonify(error="An unexpected error occurred", code="internal_error", request_id=request.environ.get("aptitude.request_id")), 500

    @app.get("/health")
    def health():
        db.session.execute(db.text("SELECT 1"))
        return {"status": "ok", "database": "mysql"}

    @app.get("/ready")
    def ready():
        from .services.operations_service import operations_snapshot
        snapshot=operations_snapshot(stale_seconds=app.config["WORKER_STALE_SECONDS"])
        worker_ready=any(worker["online"] for worker in snapshot["workers"])
        # Complete question batches are prepared by the web process before a
        # test becomes ready. The worker remains responsible for analytics.
        ready_now=worker_ready
        return {"status":"ready" if ready_now else "not_ready","database":"mysql","worker_ready":worker_ready,"question_generation":"openai_complete_batch","pending_jobs":snapshot["jobs"]["pending"]},200 if ready_now else 503

    @app.get("/")
    def index():
        if frontend_dist.joinpath("index.html").exists():
            return send_from_directory(frontend_dist, "index.html")
        return {"message": "Aptitude AI API", "frontend": "Run npm run dev in frontend"}

    return app
