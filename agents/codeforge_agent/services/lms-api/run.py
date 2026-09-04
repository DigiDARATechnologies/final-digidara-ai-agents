import os
from pathlib import Path

from waitress import serve


def load_local_env():
    path = Path(__file__).with_name(".env.local")
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


if __name__ == "__main__":
    load_local_env()
    from lms_api import create_app

    serve(create_app(), host="127.0.0.1", port=int(os.getenv("PORT", "4000")), threads=8)
