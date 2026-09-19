from .student import bp as student
from .dashboard import bp as dashboard
from .assessment import bp as assessment
from .history import bp as history
from .analytics import bp as analytics
from .usage import bp as usage
from .auth import bp as auth
from .operations import bp as operations
from .mixed_test_config import bp as mixed_test_config
from .invoke import bp as invoke
from .privacy import bp as privacy


def register_blueprints(app):
    for blueprint in (auth,student,dashboard,assessment,history,analytics,usage,operations,mixed_test_config,invoke,privacy):app.register_blueprint(blueprint)
