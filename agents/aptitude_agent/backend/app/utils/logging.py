import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {"timestamp": self.formatTime(record), "level": record.levelname, "message": record.getMessage(), "logger": record.name}
        if record.exc_info:
            # logger.exception() used to lose its traceback here, so a 500
            # ("Unhandled request error") never said where it came from.
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def configure_logging(app):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

