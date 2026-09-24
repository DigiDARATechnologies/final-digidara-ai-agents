import json
import os
from pathlib import Path
import sys

import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lms_api.catalog import COURSES, COURSE_TECHNOLOGIES, TECHNOLOGIES, TOPICS, objectives, slugify, topic_description
from lms_api.problem_catalog import PROBLEMS


def load_local_env():
    path = ROOT / ".env.local"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def connect():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"), port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.environ["MYSQL_USER"], password=os.environ["MYSQL_PASSWORD"],
        database=os.getenv("MYSQL_DATABASE", "leetcode"), charset="utf8mb4", autocommit=False,
    )


def seed():
    with connect() as conn:
        with conn.cursor() as cursor:
            for name, slug, description, icon, order in COURSES:
                cursor.execute(
                    "INSERT INTO coding_courses (name, slug, description, icon_key, display_order) VALUES (%s,%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description), icon_key=VALUES(icon_key), display_order=VALUES(display_order)",
                    (name, slug, description, icon, order),
                )
            for name, slug, description, icon, order in TECHNOLOGIES:
                cursor.execute(
                    "INSERT INTO coding_technologies (name, slug, description, icon_key, display_order) VALUES (%s,%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description), icon_key=VALUES(icon_key), display_order=VALUES(display_order)",
                    (name, slug, description, icon, order),
                )

            cursor.execute("SELECT id, slug, name FROM coding_technologies")
            technologies = {row[1]: {"id": row[0], "name": row[2]} for row in cursor.fetchall()}
            cursor.execute("SELECT id, slug FROM coding_courses")
            courses = {row[1]: row[0] for row in cursor.fetchall()}

            for course_slug, technology_slugs in COURSE_TECHNOLOGIES.items():
                for order, technology_slug in enumerate(technology_slugs, start=1):
                    cursor.execute(
                        "INSERT INTO course_technologies (course_id, technology_id, display_order) VALUES (%s,%s,%s) "
                        "ON DUPLICATE KEY UPDATE display_order=VALUES(display_order), is_active=TRUE",
                        (courses[course_slug], technologies[technology_slug]["id"], order),
                    )

            for technology_slug, names in TOPICS.items():
                technology = technologies[technology_slug]
                for order, name in enumerate(names, start=1):
                    description = topic_description(technology["name"], name)
                    cursor.execute(
                        "INSERT INTO coding_topics (technology_id, name, slug, description, learning_objectives, suggested_concepts, display_order) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description), "
                        "learning_objectives=VALUES(learning_objectives), suggested_concepts=VALUES(suggested_concepts), display_order=VALUES(display_order), is_active=TRUE",
                        (technology["id"], name, slugify(name), description, json.dumps(objectives(technology["name"], name)), json.dumps([name]), order),
                    )

            cursor.execute(
                "SELECT tp.id,t.slug,tp.slug FROM coding_topics tp JOIN coding_technologies t ON t.id=tp.technology_id"
            )
            topic_ids = {(row[1], row[2]): row[0] for row in cursor.fetchall()}
            for problem in PROBLEMS:
                topic_id = topic_ids[(problem["technology"], problem["topic"])]
                question_type = problem.get("question_type", "code")
                mcq_options = problem.get("mcq_options")
                cursor.execute(
                    "INSERT INTO coding_problems (topic_id,name,slug,description,input_format,output_format,constraints_text,examples_json,starter_code,language_key,judge0_language_id,question_type,mcq_options_json,mcq_correct_key,mcq_explanation,difficulty,max_score,display_order) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,100,%s) ON DUPLICATE KEY UPDATE name=VALUES(name),description=VALUES(description),input_format=VALUES(input_format),"
                    "output_format=VALUES(output_format),constraints_text=VALUES(constraints_text),examples_json=VALUES(examples_json),starter_code=VALUES(starter_code),language_key=VALUES(language_key),"
                    "judge0_language_id=VALUES(judge0_language_id),question_type=VALUES(question_type),mcq_options_json=VALUES(mcq_options_json),mcq_correct_key=VALUES(mcq_correct_key),"
                    "mcq_explanation=VALUES(mcq_explanation),difficulty=VALUES(difficulty),max_score=VALUES(max_score),display_order=VALUES(display_order),is_active=TRUE",
                    (topic_id, problem["name"], problem["slug"], problem["description"], problem["input_format"], problem["output_format"], problem["constraints"], json.dumps(problem["examples"]), problem.get("starter"), problem.get("language"), problem.get("language_id"), question_type, json.dumps(mcq_options) if mcq_options else None, problem.get("mcq_correct_key"), problem.get("mcq_explanation"), problem["difficulty"], problem["order"]),
                )
                problem_id = cursor.lastrowid
                if not problem_id:
                    cursor.execute("SELECT id FROM coding_problems WHERE topic_id=%s AND slug=%s", (topic_id, problem["slug"]))
                    problem_id = cursor.fetchone()[0]
                for order, (stdin_text, expected_output, hidden, weight) in enumerate(problem.get("tests", []), start=1):
                    cursor.execute(
                        "INSERT INTO coding_test_cases (problem_id,stdin_text,expected_output,is_hidden,score_weight,display_order) VALUES (%s,%s,%s,%s,%s,%s) "
                        "ON DUPLICATE KEY UPDATE stdin_text=VALUES(stdin_text),expected_output=VALUES(expected_output),is_hidden=VALUES(is_hidden),score_weight=VALUES(score_weight)",
                        (problem_id, stdin_text, expected_output, hidden, weight, order),
                    )
        conn.commit()
    print("Module 1 catalog seeded")


if __name__ == "__main__":
    load_local_env()
    seed()
