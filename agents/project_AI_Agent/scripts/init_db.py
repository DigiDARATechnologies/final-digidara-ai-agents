"""Run once to create all tables: python -m scripts.init_db"""
from app.db.database import init_db

if __name__ == "__main__":
    init_db()
    print("Database tables created.")
