from logging.config import fileConfig
from flask import current_app
from alembic import context
from backend.app.extensions import db
from backend.app.models import load_models

config=context.config
if config.config_file_name is not None:fileConfig(config.config_file_name)
load_models()
target_metadata=db.metadata

def get_engine():return db.engine
def get_url():return str(get_engine().url).replace("%","%%")

def run_migrations_offline():
    context.configure(url=get_url(),target_metadata=target_metadata,literal_binds=True,compare_type=True)
    with context.begin_transaction():context.run_migrations()

def run_migrations_online():
    with get_engine().connect() as connection:
        context.configure(connection=connection,target_metadata=target_metadata,compare_type=True)
        with context.begin_transaction():context.run_migrations()

if context.is_offline_mode():run_migrations_offline()
else:run_migrations_online()

