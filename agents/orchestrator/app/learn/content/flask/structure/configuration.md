---
title: Configuration and environments
summary: Keep settings out of the code with config classes and environment variables, and never commit secrets.
takeaways:
- Different environments (development, testing, production) need different settings
- Read secrets from environment variables, not from the code
- Use config classes and load the one you need
---
## One app, several environments

| Setting | Development | Testing | Production |
| --- | --- | --- | --- |
| `DEBUG` | on | off | **off** |
| database | a local file | in-memory | a managed server |
| `SECRET_KEY` | any value | any value | long, random, **secret** |

Flask holds settings in `app.config`, a dictionary.

## Config classes

```python
import os
from flask import Flask

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///dev.db")
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024        # reject uploads over 2 MB

class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"       # an in-memory database

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True                # send the cookie over HTTPS only
    SESSION_COOKIE_HTTPONLY = True              # hide it from JavaScript
    SESSION_COOKIE_SAMESITE = "Lax"             # limit cross-site sending

CONFIGS = {"development": DevelopmentConfig, "testing": TestingConfig, "production": ProductionConfig}

def create_app(name=None):
    app = Flask(__name__)
    app.config.from_object(CONFIGS[name or os.environ.get("APP_ENV", "development")])
    return app

for env in ("development", "testing", "production"):
    a = create_app(env)
    print(env, "| debug:", a.config["DEBUG"], "| db:", a.config["SQLALCHEMY_DATABASE_URI"], "| secure cookie:", a.config.get("SESSION_COOKIE_SECURE", False))
```

```output
development | debug: True | db: sqlite:///dev.db | secure cookie: False
testing | debug: False | db: sqlite:// | secure cookie: False
production | debug: False | db: sqlite:///dev.db | secure cookie: True
```

## Environment variables and .env files

Secrets (passwords, API keys, the database URL) must **not** be written in the code or committed to Git. Put them in the environment:

```py
# .env  (add this file to .gitignore!)
SECRET_KEY=3f9c...a long random value...
DATABASE_URL=postgresql://user:pass@db-host/skilldara
```

```py
pip install python-dotenv      # Flask loads .env automatically when it is installed
```

Make a strong key once with Python:

```python
import secrets

key = secrets.token_hex(32)
print(len(key), "characters, for example:", key[:8] + "...")
```

```output
64 characters, for example: b1c98e57...
```

## Loading from files and the environment

```python
app = Flask(__name__)
os.environ["MYAPP_GREETING"] = "Hello from the environment"
app.config.from_prefixed_env("MYAPP")          # reads MYAPP_* variables
print(app.config["GREETING"])
```

```output
Hello from the environment
```

:::warning
If a secret ever reaches Git, even for a moment, treat it as leaked: **rotate it** (create a new one), because deleting the commit does not remove copies others may already have.
:::

:::interview
**Interviewers often ask:** "Where do you keep secrets in a Flask app?" In environment variables or a secrets manager, loaded into `app.config` at start-up, and never in the source code or the repository.
:::
