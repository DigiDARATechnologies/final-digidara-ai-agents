from flask import Flask, g, jsonify

from .config import Config
from .auth_routes import accounts
from .errors import register_error_handlers
from .repository import MySqlRepository
from .routes import coding
from .routes_invoke import invoke_bp
from .evaluation import EvaluationService
from .tutor import TutorService


def create_app(config=None, repository=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)
    from integration.agent_signing import install as install_gateway_signing
    install_gateway_signing(app, "codeforge_agent")
    if not app.config.get("TESTING"):
        Config.validate()

    app.extensions["repository"] = repository or MySqlRepository()
    app.extensions["evaluation"] = EvaluationService(app.extensions["repository"])
    app.extensions["tutor"] = TutorService()
    app.register_blueprint(accounts)
    app.register_blueprint(coding)
    app.register_blueprint(invoke_bp)
    register_error_handlers(app)

    @app.after_request
    def report_tokens_used(response):
        # Real per-call usage for the orchestrator gateway's token billing —
        # TutorService._record_usage accumulates this on `g` when the AI
        # Tutor makes an LLM call, so the gateway charges actual cost
        # instead of a flat guess. Mirrors aptitude_agent's reference
        # implementation.
        response.headers["X-Tokens-Used"] = str(g.get("tokens_used_this_request", 0))
        return response

    if not app.config.get("TESTING"):
        from integration import registry_client
        registry_client.start()

    @app.get("/health")
    def health():
        database_healthy = app.extensions["repository"].health()
        evaluator_healthy = app.extensions["evaluation"].health()
        healthy = database_healthy and evaluator_healthy
        return jsonify({
            "status": "ok" if healthy else "unavailable",
            "checks": {
                "database": "ok" if database_healthy else "unavailable",
                "judge0": "ok" if evaluator_healthy else "unavailable",
            },
        }), 200 if healthy else 503

    return app
