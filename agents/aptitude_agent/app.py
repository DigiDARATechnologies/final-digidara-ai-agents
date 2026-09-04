import os
from backend.app import create_app

app = create_app()

from backend.app.integration.registry_client import start as start_registry
start_registry()

if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=app.config["DEBUG"],
    )
