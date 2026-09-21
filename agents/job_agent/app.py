from flask import Flask, jsonify

from .db import init_job_tables
from .invoke import invoke_bp
from .routes import job_bp


def create_app(testing: bool = False) -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = testing
    from .integration.agent_signing import install as install_gateway_signing
    install_gateway_signing(app, "job_agent")

    app.register_blueprint(job_bp)
    app.register_blueprint(invoke_bp)

    if not testing:
        init_job_tables()
        from .integration import registry_client
        registry_client.start()

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "agent_name": "job_agent"})

    return app
