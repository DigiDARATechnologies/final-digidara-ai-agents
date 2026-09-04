from pathlib import Path
import os

from dotenv import load_dotenv

# For local development, the project .env must win over a stale Windows
# environment variable left behind by an earlier server run. Production keeps
# its deployment-provided environment variables authoritative.
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_ENV") != "production"
    # The Flask reloader starts a second process and can make Windows startup
    # look like a failed restart when the parent process is interrupted. Keep
    # the server single-process by default; developers can opt in when needed.
    use_reloader = os.getenv("FLASK_RELOAD", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    app.run(host=host, port=port, debug=debug, use_reloader=use_reloader)
