import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({"timestamp": self.formatTime(record), "level": record.levelname, "message": record.getMessage(), "logger": record.name}, ensure_ascii=False)


def configure_logging(app):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

