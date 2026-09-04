import click

from .extensions import db
from .models import Topic

SPEAKING_TOPICS = [
    ("My Family", "Talk about your family members and home life", "easy"),
    ("My Daily Routine", "Describe what you do on a normal day", "easy"),
    ("My Favourite Food", "Talk about food you like and why", "easy"),
    ("My Hobby", "Describe a hobby you enjoy", "easy"),
    ("My Hometown", "Talk about your city, town, or village", "easy"),
    ("My Best Friend", "Describe your friend and your friendship", "easy"),
    ("My Career Goal", "Explain your future career plans", "medium"),
    ("My College Experience", "Discuss learning, friends, and campus life", "medium"),
    ("My Current Project", "Explain a project you are working on", "medium"),
    ("Importance of Communication", "Discuss why communication skills matter", "medium"),
    ("Time Management", "Talk about planning and using time well", "medium"),
    ("Learning New Skills", "Discuss how people learn and improve", "medium"),
    ("Impact of Artificial Intelligence", "Analyze how AI affects work and society", "hard"),
    ("Remote Work Versus Office Work", "Compare remote and office work communication", "hard"),
    ("Leadership and Communication", "Discuss communication in leadership", "hard"),
    ("Ethical Challenges in Technology", "Explore technology ethics and responsibility", "hard"),
    ("Future of Education", "Discuss how education may change", "hard"),
    ("Workplace Conflict Resolution", "Discuss handling disagreement professionally", "hard"),
]

WRITING_TOPICS = [
    ("Favorite Hobby", "Write about a hobby and why you enjoy it", "easy"),
    ("My Daily Routine", "Write about a normal day in your life", "easy"),
    ("My Best Friend", "Describe a close friend", "easy"),
    ("My Favourite Food", "Write about food you enjoy", "easy"),
    ("Social Media Impact", "Write about how social media affects society", "medium"),
    ("Remote Work", "Write about the pros and cons of working from home", "medium"),
    ("Time Management", "Explain how people can manage time better", "medium"),
    ("Learning New Skills", "Write about how you learn something new", "medium"),
    ("Education System", "Write about strengths and weaknesses of education today", "hard"),
    ("Future of Cities", "Write about how cities might change in the future", "hard"),
    ("Impact of Artificial Intelligence", "Analyze how AI affects work and society", "hard"),
    ("Ethical Challenges in Technology", "Write about responsibility in technology", "hard"),
]


def register_commands(app):
    @app.cli.command("init-db")
    def init_db():
        """Create all tables in the connected MySQL database."""
        db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("seed-topics")
    def seed_topics():
        """Insert a starter set of speaking/writing topics."""
        inserted = 0
        for title, description, difficulty in SPEAKING_TOPICS:
            existing = Topic.query.filter_by(category="speaking", title=title).first()
            if existing:
                existing.description = description
                existing.difficulty = difficulty
            else:
                db.session.add(Topic(category="speaking", title=title, description=description, difficulty=difficulty))
                inserted += 1
        for title, description, difficulty in WRITING_TOPICS:
            existing = Topic.query.filter_by(category="writing", title=title).first()
            if existing:
                existing.description = description
                existing.difficulty = difficulty
            else:
                db.session.add(Topic(category="writing", title=title, description=description, difficulty=difficulty))
                inserted += 1

        db.session.commit()
        click.echo(f"Seeded topics. Inserted {inserted} new topic(s); existing topics were updated.")
