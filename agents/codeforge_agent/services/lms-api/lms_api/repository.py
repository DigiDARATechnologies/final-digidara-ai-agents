import json
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from .db import connection
from .errors import ApiError


class MySqlRepository:
    def register_account(self, email, password, display_name):
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT id FROM students WHERE email=%s", (email,))
            if cursor.fetchone():
                raise ApiError("An account already exists for this email.", 409, "email_exists")
            cursor.execute(
                "INSERT INTO students (external_user_id,email,password_hash,display_name) VALUES (%s,%s,%s,%s)",
                (f"local:{uuid.uuid4().hex}", email, generate_password_hash(password, method="scrypt"), display_name),
            )
            student_id = cursor.lastrowid
            conn.commit()
        return self._start_session(student_id)

    def login_account(self, email, password):
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT * FROM students WHERE email=%s", (email,))
            row = cursor.fetchone()
        valid = bool(row and row.get("password_hash") and check_password_hash(row["password_hash"], password))
        if not valid:
            raise ApiError("Email or password is incorrect.", 401, "invalid_credentials")
        if not row["is_active"]:
            raise ApiError("This student account is inactive.", 403, "inactive_student")
        return self._start_session(row["id"])

    def _start_session(self, student_id):
        token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires = datetime.now(timezone.utc) + timedelta(days=current_app.config["SESSION_DAYS"])
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute("DELETE FROM student_sessions WHERE expires_at < UTC_TIMESTAMP() OR revoked_at IS NOT NULL")
            cursor.execute(
                "INSERT INTO student_sessions (student_id,token_hash,expires_at) VALUES (%s,%s,%s)",
                (student_id, token_hash, expires.replace(tzinfo=None)),
            )
            cursor.execute("SELECT * FROM students WHERE id=%s", (student_id,))
            student = self._student(cursor.fetchone())
            conn.commit()
        return student, token, expires.isoformat()

    def student_for_session(self, token):
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT s.* FROM student_sessions ss JOIN students s ON s.id=ss.student_id "
                "WHERE ss.token_hash=%s AND ss.revoked_at IS NULL AND ss.expires_at>UTC_TIMESTAMP()",
                (token_hash,),
            )
            row = cursor.fetchone()
            if row:
                cursor.execute("UPDATE student_sessions SET last_seen_at=UTC_TIMESTAMP() WHERE token_hash=%s", (token_hash,))
                conn.commit()
        return self._student(row) if row else None

    def revoke_session(self, token):
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute("UPDATE student_sessions SET revoked_at=UTC_TIMESTAMP() WHERE token_hash=%s", (token_hash,))
            conn.commit()

    def claim_request(self, request_id, timestamp):
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute("DELETE FROM api_request_nonces WHERE created_at < UTC_TIMESTAMP() - INTERVAL 10 MINUTE")
            cursor.execute(
                "INSERT IGNORE INTO api_request_nonces (request_id, requested_at) VALUES (%s, %s)",
                (request_id, timestamp),
            )
            claimed = cursor.rowcount == 1
            conn.commit()
            return claimed

    def ensure_student(self, external_user_id, email, display_name):
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM students WHERE external_user_id = %s OR email = %s FOR UPDATE",
                (external_user_id, email),
            )
            student = cursor.fetchone()
            if student:
                cursor.execute(
                    "UPDATE students SET external_user_id=%s, email=%s, display_name=CASE WHEN display_name=email THEN %s ELSE display_name END WHERE id=%s",
                    (external_user_id, email, display_name, student["id"]),
                )
            else:
                cursor.execute(
                    "INSERT INTO students (external_user_id, email, display_name) VALUES (%s,%s,%s)",
                    (external_user_id, email, display_name),
                )
            cursor.execute("SELECT * FROM students WHERE external_user_id=%s", (external_user_id,))
            student = cursor.fetchone()
            conn.commit()
            return self._student(student)

    def ensure_session(self, external_user_id, email, display_name):
        """Passwordless provisioning + login for a trusted external identity
        (the DigiDARA gateway). Composes the existing ensure_student upsert
        with the same _start_session used by register/login."""
        student = self.ensure_student(external_user_id, email, display_name)
        return self._start_session(student["id"])

    def health(self):
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT 1 AS healthy")
            return cursor.fetchone()["healthy"] == 1

    def dashboard(self, student_id):
        courses = self.list_courses(student_id)
        return {"courses": courses, "continue": self.continue_destination(student_id)}

    def list_courses(self, student_id):
        del student_id
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT c.id,c.name,c.slug,c.description,c.icon_key,COUNT(t.id) AS technology_count "
                "FROM coding_courses c LEFT JOIN course_technologies ct ON ct.course_id=c.id AND ct.is_active=TRUE "
                "LEFT JOIN coding_technologies t ON t.id=ct.technology_id AND t.is_active=TRUE "
                "WHERE c.is_active=TRUE GROUP BY c.id ORDER BY c.display_order,c.id"
            )
            return [self._course(row) for row in cursor.fetchall()]

    def get_course(self, course_slug):
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT c.id,c.name,c.slug,c.description,c.icon_key,COUNT(t.id) AS technology_count "
                "FROM coding_courses c LEFT JOIN course_technologies ct ON ct.course_id=c.id AND ct.is_active=TRUE "
                "LEFT JOIN coding_technologies t ON t.id=ct.technology_id AND t.is_active=TRUE "
                "WHERE c.slug=%s AND c.is_active=TRUE GROUP BY c.id",
                (course_slug,),
            )
            row = cursor.fetchone()
            if not row:
                raise ApiError("The coding course is unavailable.", 404, "course_not_found")
            return self._course(row)

    def list_technologies(self, course_slug):
        course = self.get_course(course_slug)
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT t.id,t.name,t.slug,t.description,t.icon_key,COUNT(tp.id) AS topic_count "
                "FROM course_technologies ct JOIN coding_technologies t ON t.id=ct.technology_id "
                "LEFT JOIN coding_topics tp ON tp.technology_id=t.id AND tp.is_active=TRUE "
                "WHERE ct.course_id=%s AND ct.is_active=TRUE AND t.is_active=TRUE "
                "GROUP BY t.id,ct.display_order ORDER BY ct.display_order,t.id",
                (course["id"],),
            )
            return course, [self._technology(row) for row in cursor.fetchall()]

    def list_topics(self, course_slug, technology_slug, student_id=None):
        course, technologies = self.list_technologies(course_slug)
        technology = next((item for item in technologies if item["slug"] == technology_slug), None)
        if not technology:
            raise ApiError("The technology is unavailable for this course.", 404, "technology_not_found")
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT tp.id,tp.name,tp.slug,tp.description,tp.display_order,COUNT(DISTINCT p.id) problem_count,"
                "COUNT(DISTINCT CASE WHEN spp.status='Solved' THEN p.id END) solved_count,"
                "COUNT(DISTINCT CASE WHEN spp.attempts>0 THEN p.id END) attempted_count "
                "FROM coding_topics tp LEFT JOIN coding_problems p ON p.topic_id=tp.id AND p.is_active=TRUE "
                "LEFT JOIN student_problem_progress spp ON spp.problem_id=p.id AND spp.student_id=%s "
                "WHERE tp.technology_id=%s AND tp.is_active=TRUE GROUP BY tp.id ORDER BY tp.display_order,tp.id",
                (student_id or 0, technology["id"]),
            )
            topics = [self._topic_summary(row) for row in cursor.fetchall()]
        return course, technology, topics

    def get_topic(self, course_slug, technology_slug, topic_slug):
        course, technology, topics = self.list_topics(course_slug, technology_slug)
        topic_index = next((index for index, item in enumerate(topics) if item["slug"] == topic_slug), None)
        if topic_index is None:
            raise ApiError("The coding topic is unavailable.", 404, "topic_not_found")
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT id,name,slug,description,learning_objectives,suggested_concepts,display_order "
                "FROM coding_topics WHERE technology_id=%s AND slug=%s AND is_active=TRUE",
                (technology["id"], topic_slug),
            )
            row = cursor.fetchone()
        topic = self._topic_summary(row)
        topic["learning_objectives"] = self._json_list(row["learning_objectives"])
        topic["suggested_concepts"] = self._json_list(row["suggested_concepts"])
        topic["previous"] = topics[topic_index - 1] if topic_index > 0 else None
        topic["next"] = topics[topic_index + 1] if topic_index + 1 < len(topics) else None
        return course, technology, topic

    def list_problems(self, student_id, course_slug, technology_slug, topic_slug):
        course, technology, topic = self.get_topic(course_slug, technology_slug, topic_slug)
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT p.id,p.name,p.slug,p.description,p.difficulty,p.max_score,p.language_key,p.question_type,p.display_order,"
                "COALESCE(spp.status,'Not Started') progress,COALESCE(spp.best_score,0) best_score,COALESCE(spp.attempts,0) attempts "
                "FROM coding_problems p LEFT JOIN student_problem_progress spp ON spp.problem_id=p.id AND spp.student_id=%s "
                "WHERE p.topic_id=%s AND p.is_active=TRUE ORDER BY p.display_order,p.id",
                (student_id, topic["id"]),
            )
            problems = [self._problem_summary(row) for row in cursor.fetchall()]
        return course, technology, topic, problems

    def get_problem(self, student_id, course_slug, technology_slug, topic_slug, problem_slug):
        course, technology, topic, problems = self.list_problems(student_id, course_slug, technology_slug, topic_slug)
        summary = next((problem for problem in problems if problem["slug"] == problem_slug), None)
        if not summary:
            raise ApiError("The coding problem is unavailable.", 404, "problem_not_found")
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT * FROM coding_problems WHERE id=%s AND is_active=TRUE", (summary["id"],))
            row = cursor.fetchone()
            if row["question_type"] == "mcq":
                # Never the correct key/explanation here -- those are only
                # revealed in the submit_mcq_answer response, same as an
                # execution problem's hidden test cases aren't shown upfront.
                problem = {**summary, "options": self._json_dict(row["mcq_options_json"])}
                return course, technology, topic, problem
            cursor.execute(
                "SELECT id,stdin_text,expected_output,display_order FROM coding_test_cases "
                "WHERE problem_id=%s AND is_hidden=FALSE ORDER BY display_order",
                (summary["id"],),
            )
            public_cases = [
                {"id": case["id"], "input": case["stdin_text"], "expectedOutput": case["expected_output"], "sequence": case["display_order"]}
                for case in cursor.fetchall()
            ]
        problem = {**summary, "input_format": row["input_format"], "output_format": row["output_format"],
                   "constraints": row["constraints_text"], "examples": self._json_list(row["examples_json"]),
                   "starter_code": row["starter_code"], "judge0_language_id": row["judge0_language_id"],
                   "public_tests": public_cases}
        return course, technology, topic, problem

    def submit_mcq_answer(self, student_id, problem_id, selected_key):
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM coding_problems WHERE id=%s AND is_active=TRUE AND question_type='mcq'",
                (problem_id,),
            )
            problem = cursor.fetchone()
        if not problem:
            raise ApiError("The coding problem is unavailable.", 404, "problem_not_found")
        options = self._json_dict(problem["mcq_options_json"])
        if selected_key not in options:
            raise ApiError("selectedKey is invalid.", 400, "invalid_parameter")
        correct = selected_key == problem["mcq_correct_key"]
        outcome = {
            "status": "Accepted" if correct else "Wrong Answer",
            "score": problem["max_score"] if correct else 0,
            "isCorrect": correct,
            "correctKey": problem["mcq_correct_key"],
            "explanation": problem["mcq_explanation"] or "",
            "passedTests": 1 if correct else 0,
            "totalTests": 1,
            "tests": [],
        }
        submission_id = self.save_submission(student_id, problem, f"Selected: {selected_key}", "submit", outcome)
        return {"submissionId": submission_id, "mode": "submit", **outcome}

    def problem_for_evaluation(self, student_id, problem_id):
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT p.*,tp.name topic_name,t.name technology_name FROM coding_problems p "
                "JOIN coding_topics tp ON tp.id=p.topic_id JOIN coding_technologies t ON t.id=tp.technology_id "
                "WHERE p.id=%s AND p.is_active=TRUE AND tp.is_active=TRUE AND t.is_active=TRUE",
                (problem_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise ApiError("The coding problem is unavailable.", 404, "problem_not_found")
        del student_id
        return row

    def evaluation_cases(self, problem_id, include_hidden):
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT id,stdin_text,expected_output,is_hidden,score_weight,display_order FROM coding_test_cases "
                "WHERE problem_id=%s AND (%s=TRUE OR is_hidden=FALSE) ORDER BY display_order",
                (problem_id, include_hidden),
            )
            return cursor.fetchall()

    def save_submission(self, student_id, problem, source_code, mode, outcome):
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO coding_submissions (student_id,problem_id,source_code,language_key,mode,status,score,passed_tests,total_tests,result_json) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (student_id, problem["id"], source_code, problem["language_key"], mode, outcome["status"], outcome["score"],
                 outcome["passedTests"], outcome["totalTests"], json.dumps(outcome["tests"])),
            )
            submission_id = cursor.lastrowid
            if mode == "submit":
                solved = outcome["score"] == problem["max_score"]
                cursor.execute(
                    "INSERT INTO student_problem_progress (student_id,problem_id,attempts,best_score,status,last_submission_id,first_solved_at) "
                    "VALUES (%s,%s,1,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE attempts=attempts+1,best_score=GREATEST(best_score,VALUES(best_score)),"
                    "status=IF(GREATEST(best_score,VALUES(best_score))>=%s,'Solved','Attempted'),last_submission_id=VALUES(last_submission_id),"
                    "first_solved_at=COALESCE(first_solved_at,VALUES(first_solved_at))",
                    (student_id, problem["id"], outcome["score"], "Solved" if solved else "Attempted", submission_id,
                     datetime.now(timezone.utc).replace(tzinfo=None) if solved else None, problem["max_score"]),
                )
            conn.commit()
        return submission_id

    def get_submission(self, student_id, problem_id, submission_id):
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM coding_submissions WHERE id=%s AND student_id=%s AND problem_id=%s",
                (submission_id, student_id, problem_id),
            )
            row = cursor.fetchone()
        if not row:
            raise ApiError("The submission is unavailable.", 404, "submission_not_found")
        row["result_json"] = self._json_list(row["result_json"])
        return row

    def save_tutor_interaction(self, student_id, problem_id, submission_id, category, explanation):
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tutor_interactions (student_id,problem_id,submission_id,error_category,explanation) VALUES (%s,%s,%s,%s,%s)",
                (student_id, problem_id, submission_id, category, explanation),
            )
            conn.commit()

    def progress_summary(self, student_id):
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(p.id) total_problems,COUNT(CASE WHEN spp.status='Solved' THEN 1 END) solved_problems,"
                "COALESCE(ROUND(AVG(COALESCE(spp.best_score,0))),0) average_score "
                "FROM coding_problems p LEFT JOIN student_problem_progress spp ON spp.problem_id=p.id AND spp.student_id=%s WHERE p.is_active=TRUE",
                (student_id,),
            )
            row = cursor.fetchone()
        return {"totalProblems": int(row["total_problems"]), "solvedProblems": int(row["solved_problems"]), "averageScore": int(row["average_score"])}

    def record_activity(self, student_id, course_slug, technology_slug=None, topic_slug=None):
        course = self.get_course(course_slug)
        technology = None
        topic = None
        if technology_slug:
            _, technologies = self.list_technologies(course_slug)
            technology = next((item for item in technologies if item["slug"] == technology_slug), None)
            if not technology:
                raise ApiError("The technology is unavailable for this course.", 404, "technology_not_found")
        if topic_slug:
            if not technology:
                raise ApiError("technologySlug is required with topicSlug.", 400, "invalid_activity")
            _, _, topic = self.get_topic(course_slug, technology_slug, topic_slug)
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO student_coding_activity (student_id,course_id,technology_id,topic_id) VALUES (%s,%s,%s,%s)",
                (student_id, course["id"], technology["id"] if technology else None, topic["id"] if topic else None),
            )
            created = cursor.lastrowid
            conn.commit()
        return {"id": created, "destination": self._destination(course, technology, topic)}

    def continue_destination(self, student_id):
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT c.name course_name,c.slug course_slug,t.name technology_name,t.slug technology_slug,"
                "tp.name topic_name,tp.slug topic_slug,a.last_accessed_at "
                "FROM student_coding_activity a JOIN coding_courses c ON c.id=a.course_id "
                "LEFT JOIN coding_technologies t ON t.id=a.technology_id "
                "LEFT JOIN coding_topics tp ON tp.id=a.topic_id "
                "WHERE a.student_id=%s AND c.is_active=TRUE ORDER BY a.last_accessed_at DESC,a.id DESC LIMIT 1",
                (student_id,),
            )
            row = cursor.fetchone()
        if not row:
            return {"label": "Coding Practice", "href": "/coding", "kind": "dashboard"}
        course = {"name": row["course_name"], "slug": row["course_slug"]}
        technology = {"name": row["technology_name"], "slug": row["technology_slug"]} if row["technology_slug"] else None
        topic = {"name": row["topic_name"], "slug": row["topic_slug"]} if row["topic_slug"] else None
        return self._destination(course, technology, topic)

    def get_profile(self, student_id):
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT * FROM students WHERE id=%s", (student_id,))
            return self._student(cursor.fetchone())

    def update_profile(self, student_id, display_name, bio, timezone):
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "UPDATE students SET display_name=%s,bio=%s,timezone=%s WHERE id=%s",
                (display_name, bio or None, timezone, student_id),
            )
            conn.commit()
        return self.get_profile(student_id)

    @staticmethod
    def _student(row):
        return {
            "id": row["id"], "email": row["email"], "display_name": row["display_name"],
            "bio": row.get("bio"), "timezone": row["timezone"], "is_active": bool(row["is_active"]),
        }

    @staticmethod
    def _course(row):
        return {"id": row["id"], "name": row["name"], "slug": row["slug"], "description": row["description"], "icon": row["icon_key"], "technology_count": int(row["technology_count"])}

    @staticmethod
    def _technology(row):
        return {"id": row["id"], "name": row["name"], "slug": row["slug"], "description": row["description"], "icon": row["icon_key"], "topic_count": int(row["topic_count"])}

    @staticmethod
    def _topic_summary(row):
        problem_count = int(row.get("problem_count", 0))
        solved_count = int(row.get("solved_count", 0))
        attempted_count = int(row.get("attempted_count", 0))
        progress = "Solved" if problem_count and solved_count == problem_count else "In Progress" if attempted_count else "Not Started"
        return {"id": row["id"], "name": row["name"], "slug": row["slug"], "description": row["description"], "sequence": int(row["display_order"]), "problem_count": problem_count, "progress": progress}

    @staticmethod
    def _problem_summary(row):
        return {"id": row["id"], "name": row["name"], "slug": row["slug"], "description": row["description"],
                "difficulty": row["difficulty"], "max_score": int(row["max_score"]), "language": row["language_key"],
                "question_type": row.get("question_type", "code"),
                "sequence": int(row["display_order"]), "progress": row.get("progress", "Not Started"),
                "best_score": int(row.get("best_score", 0)), "attempts": int(row.get("attempts", 0))}

    def record_llm_usage(self, provider, model_name, prompt_tokens, completion_tokens, total_tokens, request_type, user_id=None):
        """Best-effort — a usage-logging failure must never break the AI
        Tutor call it's attached to. `user_id` is the verified DigiDARA
        identity (`X-DigiDARA-User-Id`, forwarded by the orchestrator
        gateway) that triggered the call, so usage can be reported per user
        instead of as a platform-wide total."""
        try:
            with connection() as conn, conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO llm_usage
                         (user_id, provider, model_name, prompt_tokens, completion_tokens, total_tokens, request_type)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (user_id, provider, model_name, prompt_tokens, completion_tokens, total_tokens, request_type),
                )
                conn.commit()
        except Exception:
            current_app.logger.warning("failed to record LLM usage", exc_info=True)

    def get_llm_usage_summary(self, user_id=None):
        """Token usage for this agent, scoped to the verified DigiDARA
        identity that made the calls — backs the Settings > Usage dashboard.
        Without a verified identity there is nothing safe to attribute the
        request to, so this returns all-zero totals rather than a
        platform-wide aggregate."""
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                """SELECT COUNT(*) AS total_requests,
                          COALESCE(SUM(prompt_tokens),0) AS prompt_tokens,
                          COALESCE(SUM(completion_tokens),0) AS completion_tokens,
                          COALESCE(SUM(total_tokens),0) AS total_tokens
                   FROM llm_usage WHERE user_id = %s""",
                (user_id,),
            )
            totals = cursor.fetchone()
            cursor.execute(
                "SELECT request_type, COALESCE(SUM(total_tokens),0) AS tokens FROM llm_usage WHERE user_id = %s GROUP BY request_type",
                (user_id,),
            )
            # `user_id = NULL` never matches in SQL, so an unverified caller
            # naturally gets all-zero totals and an empty breakdown here.
            by_type = cursor.fetchall()
        return {
            "agent_name": "codeforge_agent",
            "total_requests": totals["total_requests"],
            "total_tokens": int(totals["total_tokens"]),
            "prompt_tokens": int(totals["prompt_tokens"]),
            "completion_tokens": int(totals["completion_tokens"]),
            "by_request_type": {row["request_type"]: int(row["tokens"]) for row in by_type},
        }

    @staticmethod
    def _json_list(value):
        if isinstance(value, list):
            return value
        return json.loads(value) if value else []

    @staticmethod
    def _json_dict(value):
        if isinstance(value, dict):
            return value
        return json.loads(value) if value else {}

    @staticmethod
    def _destination(course, technology=None, topic=None):
        href = f"/coding/courses/{course['slug']}"
        label = course["name"]
        kind = "course"
        if technology:
            href += f"/{technology['slug']}"
            label = technology["name"]
            kind = "technology"
        if topic:
            href += f"/{topic['slug']}"
            label = topic["name"]
            kind = "topic"
        return {"label": label, "href": href, "kind": kind}
