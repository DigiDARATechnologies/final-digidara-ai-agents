---
title: Database migrations
summary: Change a live database safely with Flask-Migrate (Alembic), without losing data.
takeaways:
- create_all only creates missing tables; it never changes existing ones
- A migration is a versioned script that upgrades (and can downgrade) the schema
- Review every generated migration before running it
---
## The problem

`db.create_all()` only creates tables that **do not exist**. If you add a column to a model after the table exists, `create_all` ignores it, and your code fails with "no such column". Deleting the database to fix it destroys your data. In production, that is not an option.

## The solution: migrations

A **migration** is a small script that changes the schema from one version to the next. They are saved in your repository, so every environment (your laptop, a teammate, production) can reach the same structure by running them in order. **Flask-Migrate** wraps the **Alembic** tool for Flask-SQLAlchemy.

```py
pip install flask-migrate
```

```py
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    db.init_app(app)
    migrate.init_app(app, db)
    return app
```

## The daily routine

```py
flask db init                       # once per project: creates the migrations/ folder
flask db migrate -m "add phone"     # compare models with the database and write a migration script
flask db upgrade                    # run the new migrations on this database
flask db downgrade                  # undo the last migration
flask db history                    # list the migrations
```

| Step | What you do |
| --- | --- |
| 1 | change the model (add a column) |
| 2 | `flask db migrate -m "..."` |
| 3 | **open the generated file and read it** |
| 4 | `flask db upgrade` on your own database |
| 5 | commit the migration file with the code |
| 6 | run `flask db upgrade` during deployment |

## What a migration file looks like

```py
def upgrade():
    op.add_column("student", sa.Column("phone", sa.String(length=15), nullable=True))

def downgrade():
    op.drop_column("student", "phone")
```

## Safe changes on a live database

| Change | Careful approach |
| --- | --- |
| Add a column | make it **nullable**, or give it a default; adding `NOT NULL` with no default fails on existing rows |
| Rename a column | Alembic may see this as a drop and an add, which **loses data**. Edit the migration to use `op.alter_column(..., new_column_name=...)` |
| Drop a column | deploy code that no longer uses it first, then drop it in a later release |
| Big table change | test on a copy with real volume, because some changes lock the table |

:::warning
Auto-generated migrations are a **draft**. Always read them before running, especially renames and drops. Take a database **backup** before upgrading production.
:::

## Adding a required column in two steps

1. Add the column as **nullable**, deploy, and fill existing rows (a data migration or script).
2. Add a second migration that makes it `NOT NULL`.

Doing it in two small steps avoids a failure in the middle of a deployment.

:::interview
**Interviewers often ask:** "How do you change the database schema in production?" With versioned migrations (Alembic through Flask-Migrate) that are reviewed, tested, committed to Git and applied during deployment, with a backup and a plan to roll back.
:::
