"""Blueprint registration for the mock-interview API."""


def register_blueprints(app):
    from routes.answers import answers_bp
    from routes.analytics import analytics_bp
    from routes.dashboard import dashboard_bp
    from routes.history import history_bp
    from routes.interviews import interviews_bp
    from routes.profile import profile_bp
    from routes.uploads import uploads_bp
    from routes.invoke import bp as invoke_bp

    for blueprint in (
        answers_bp,
        analytics_bp,
        interviews_bp,
        dashboard_bp,
        profile_bp,
        uploads_bp,
        history_bp,
        invoke_bp,
    ):
        app.register_blueprint(blueprint, url_prefix="/api")
