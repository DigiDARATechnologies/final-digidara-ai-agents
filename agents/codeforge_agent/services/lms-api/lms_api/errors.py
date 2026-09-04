from flask import jsonify


class ApiError(Exception):
    def __init__(self, message, status=400, code="bad_request"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return jsonify({"error": {"code": error.code, "message": error.message}}), error.status

    @app.errorhandler(404)
    def handle_not_found(_error):
        return jsonify({"error": {"code": "not_found", "message": "The requested resource is unavailable."}}), 404

    @app.errorhandler(Exception)
    def handle_unexpected(error):
        app.logger.exception("Unexpected LMS API error", exc_info=error)
        return jsonify({"error": {"code": "internal_error", "message": "The service could not complete the request."}}), 500
