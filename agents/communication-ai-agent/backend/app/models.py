import json
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .utils.score_utils import to_score10


def _json_load(value, fallback=None):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _json_list(value):
    parsed = _json_load(value, [])
    return parsed if isinstance(parsed, list) else []


def _json_dict(value):
    parsed = _json_load(value, {})
    return parsed if isinstance(parsed, dict) else {}


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default="student", nullable=False)
    target_level = db.Column(db.String(30), default="Intermediate")  # Beginner/Intermediate/Advanced
    phone = db.Column(db.String(30), nullable=True)
    course_name = db.Column(db.String(120), nullable=True)
    photo_url = db.Column(db.String(300), nullable=True)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    total_xp = db.Column(db.Integer, default=0, nullable=False)
    streak_count = db.Column(db.Integer, default=0, nullable=False)
    last_completed_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "course_name": self.course_name,
            "photo_url": self.photo_url,
            "email_verified": self.email_verified,
            "total_xp": self.total_xp,
            "member_since": self.created_at.strftime("%b %Y") if self.created_at else None,
        }


class SpeakingSession(db.Model):
    __tablename__ = "speaking_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    mode = db.Column(db.String(20), nullable=False)  # 'topic' | 'daily'
    generated_topic_id = db.Column(db.String(64), nullable=True)
    topic_title = db.Column(db.String(200), nullable=True)
    topic_description = db.Column(db.String(500), nullable=True)
    daily_category = db.Column(db.String(120), nullable=True)
    session_date = db.Column(db.Date, nullable=True, index=True)
    total_questions = db.Column(db.Integer, nullable=True)
    current_question = db.Column(db.Integer, nullable=True)
    daily_questions_json = db.Column(db.Text, nullable=True)
    daily_vocabulary_json = db.Column(db.Text, nullable=True)
    daily_vocab_used_json = db.Column(db.Text, nullable=True)
    difficulty = db.Column(db.String(20), nullable=False, default="medium")
    status = db.Column(db.String(20), nullable=False, default="in_progress")  # in_progress | completed | ended_by_user
    total_turns = db.Column(db.Integer, default=0)
    answered_turns = db.Column(db.Integer, default=0)
    ended_by_user = db.Column(db.Boolean, default=False, nullable=False)

    confidence_score = db.Column(db.Float, nullable=True)
    fluency_score = db.Column(db.Float, nullable=True)
    grammar_score = db.Column(db.Float, nullable=True)
    knowledge_score = db.Column(db.Float, nullable=True)  # only meaningful for 'topic' mode
    clarity_score = db.Column(db.Float, nullable=True)
    overall_score = db.Column(db.Float, nullable=True)
    summary_feedback = db.Column(db.Text, nullable=True)
    strengths_json = db.Column(db.Text, nullable=True)
    weaknesses_json = db.Column(db.Text, nullable=True)
    common_mistakes_json = db.Column(db.Text, nullable=True)
    recommendation = db.Column(db.Text, nullable=True)
    next_practice_suggestion = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    turns = db.relationship("SpeakingTurn", backref="session", cascade="all, delete-orphan", order_by="SpeakingTurn.turn_number")

    def to_summary_dict(self):
        return {
            "id": self.id,
            "type": "speaking",
            "mode": self.mode,
            "generated_topic_id": self.generated_topic_id,
            "topic_title": self.topic_title,
            "topic_description": self.topic_description,
            "daily_category": self.daily_category,
            "session_date": self.session_date.isoformat() if self.session_date else None,
            "total_questions": self.total_questions or self.total_turns,
            "daily_vocabulary": _json_list(self.daily_vocabulary_json),
            "difficulty": self.difficulty,
            "status": self.status,
            "overall_score": to_score10(self.overall_score),
            "answered_turns": self.answered_turns,
            "total_turns": self.total_turns,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_detail_dict(self):
        data = self.to_summary_dict()
        data.update({
            "confidence_score": to_score10(self.confidence_score),
            "fluency_score": to_score10(self.fluency_score),
            "grammar_score": to_score10(self.grammar_score),
            "clarity_score": to_score10(self.clarity_score),
            "knowledge_score": to_score10(self.knowledge_score),
            "summary_feedback": self.summary_feedback,
            "strengths": _json_list(self.strengths_json),
            "areas_to_improve": _json_list(self.weaknesses_json),
            "common_mistakes": _json_list(self.common_mistakes_json),
            "recommendation": self.recommendation,
            "next_practice_suggestion": self.next_practice_suggestion,
            "session_date": self.session_date.isoformat() if self.session_date else None,
            "daily_vocabulary": _json_list(self.daily_vocabulary_json),
            "daily_vocab_used": _json_list(self.daily_vocab_used_json),
            "turns": [t.to_dict() for t in self.turns],
        })
        return data


class SpeakingTurn(db.Model):
    __tablename__ = "speaking_turns"
    __table_args__ = (
        db.UniqueConstraint("session_id", "submission_id", name="uq_speaking_turn_submission"),
    )

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("speaking_sessions.id"), nullable=False, index=True)
    turn_number = db.Column(db.Integer, nullable=False)
    ai_question = db.Column(db.Text, nullable=False)
    user_answer = db.Column(db.Text, nullable=True)
    answer_time_seconds = db.Column(db.Integer, nullable=True)
    submission_id = db.Column(db.String(160), nullable=True)
    submission_response_json = db.Column(db.Text, nullable=True)
    corrected_answer = db.Column(db.Text, nullable=True)
    better_natural_answer = db.Column(db.Text, nullable=True)
    reaction = db.Column(db.Text, nullable=True)
    natural_version = db.Column(db.Text, nullable=True)
    explanation = db.Column(db.Text, nullable=True)
    feedback_json = db.Column(db.Text, nullable=True)

    confidence_score = db.Column(db.Float, nullable=True)
    fluency_score = db.Column(db.Float, nullable=True)
    grammar_score = db.Column(db.Float, nullable=True)
    knowledge_score = db.Column(db.Float, nullable=True)
    clarity_score = db.Column(db.Float, nullable=True)
    overall_score = db.Column(db.Float, nullable=True)
    feedback = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        feedback = _json_dict(self.feedback_json)
        scores = feedback.get("scores") if isinstance(feedback.get("scores"), dict) else {}
        return {
            "turn_number": self.turn_number,
            "ai_question": self.ai_question,
            "user_answer": self.user_answer,
            "answer_time_seconds": self.answer_time_seconds,
            "corrected_answer": self.corrected_answer,
            "better_natural_answer": self.better_natural_answer,
            "reaction": self.reaction,
            "natural_version": self.natural_version,
            "feedback_json": feedback,
            "answer_status": feedback.get("status"),
            "explanation": feedback.get("explanation") or self.explanation,
            "mistakes": feedback.get("mistakes") if isinstance(feedback.get("mistakes"), list) else [],
            "vocabulary_suggestions": feedback.get("vocabulary_suggestions")
            if isinstance(feedback.get("vocabulary_suggestions"), list)
            else [],
            "confidence_score": to_score10(self.confidence_score),
            "fluency_score": to_score10(self.fluency_score),
            "grammar_score": to_score10(self.grammar_score),
            "clarity_score": to_score10(self.clarity_score),
            "knowledge_score": to_score10(self.knowledge_score),
            "overall_score": to_score10(self.overall_score),
            "scores": {
                "confidence": to_score10(scores.get("confidence", self.confidence_score)),
                "fluency": to_score10(scores.get("fluency", self.fluency_score)),
                "grammar": to_score10(scores.get("grammar", self.grammar_score)),
                "clarity": to_score10(scores.get("clarity")),
                "relevance": to_score10(scores.get("relevance")),
                "knowledge": to_score10(scores.get("knowledge", self.knowledge_score)),
                "overall": to_score10(scores.get("overall", self.overall_score)),
            },
            "feedback": self.feedback,
        }


class WritingSession(db.Model):
    __tablename__ = "writing_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    mode = db.Column(db.String(20), nullable=False)  # 'topic' | 'daily'
    generated_topic_id = db.Column(db.String(64), nullable=True)
    topic_title = db.Column(db.String(200), nullable=True)
    topic_description = db.Column(db.String(500), nullable=True)
    difficulty = db.Column(db.String(20), nullable=False, default="medium")
    status = db.Column(db.String(20), nullable=False, default="in_progress")
    total_turns = db.Column(db.Integer, default=0)

    grammar_score = db.Column(db.Float, nullable=True)
    vocabulary_score = db.Column(db.Float, nullable=True)
    clarity_score = db.Column(db.Float, nullable=True)
    knowledge_score = db.Column(db.Float, nullable=True)
    overall_score = db.Column(db.Float, nullable=True)
    summary_feedback = db.Column(db.Text, nullable=True)
    strengths_json = db.Column(db.Text, nullable=True)
    weaknesses_json = db.Column(db.Text, nullable=True)
    common_mistakes_json = db.Column(db.Text, nullable=True)
    recommendation = db.Column(db.Text, nullable=True)
    next_practice_suggestion = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    turns = db.relationship("WritingTurn", backref="session", cascade="all, delete-orphan", order_by="WritingTurn.turn_number")

    def to_summary_dict(self):
        return {
            "id": self.id,
            "type": "writing",
            "mode": self.mode,
            "generated_topic_id": self.generated_topic_id,
            "topic_title": self.topic_title,
            "topic_description": self.topic_description,
            "difficulty": self.difficulty,
            "status": self.status,
            "overall_score": to_score10(self.overall_score),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_detail_dict(self):
        data = self.to_summary_dict()
        data.update({
            "grammar_score": to_score10(self.grammar_score),
            "vocabulary_score": to_score10(self.vocabulary_score),
            "clarity_score": to_score10(self.clarity_score),
            "knowledge_score": to_score10(self.knowledge_score),
            "summary_feedback": self.summary_feedback,
            "strengths": _json_list(self.strengths_json),
            "areas_to_improve": _json_list(self.weaknesses_json),
            "common_mistakes": _json_list(self.common_mistakes_json),
            "recommendation": self.recommendation,
            "next_practice_suggestion": self.next_practice_suggestion,
            "turns": [t.to_dict() for t in self.turns],
        })
        return data


class WritingTurn(db.Model):
    __tablename__ = "writing_turns"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("writing_sessions.id"), nullable=False, index=True)
    turn_number = db.Column(db.Integer, nullable=False)
    ai_prompt = db.Column(db.Text, nullable=False)
    user_response = db.Column(db.Text, nullable=True)

    grammar_score = db.Column(db.Float, nullable=True)
    vocabulary_score = db.Column(db.Float, nullable=True)
    clarity_score = db.Column(db.Float, nullable=True)
    knowledge_score = db.Column(db.Float, nullable=True)
    overall_score = db.Column(db.Float, nullable=True)
    corrected_answer = db.Column(db.Text, nullable=True)
    better_natural_answer = db.Column(db.Text, nullable=True)
    feedback_json = db.Column(db.Text, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    draft_text = db.Column(db.Text, nullable=True)
    draft_updated_at = db.Column(db.DateTime, nullable=True)
    used_ai_suggestion = db.Column(db.Boolean, default=False, nullable=False)
    weak_area_tags = db.Column(db.Text, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        feedback = _json_dict(self.feedback_json)
        scores = feedback.get("scores") if isinstance(feedback.get("scores"), dict) else {}
        return {
            "turn_id": self.id,
            "turn_number": self.turn_number,
            "ai_prompt": self.ai_prompt,
            "user_response": self.user_response,
            "original_answer": feedback.get("original_answer") or self.user_response,
            "corrected_answer": self.corrected_answer,
            "better_natural_answer": self.better_natural_answer,
            "strengths": feedback.get("strengths") if isinstance(feedback.get("strengths"), list) else [],
            "areas_to_improve": feedback.get("areas_to_improve") if isinstance(feedback.get("areas_to_improve"), list) else [],
            "feedback_json": feedback,
            "answer_status": feedback.get("status"),
            "explanation": feedback.get("explanation"),
            "mistakes": feedback.get("mistakes") if isinstance(feedback.get("mistakes"), list) else [],
            "vocabulary_suggestions": feedback.get("vocabulary_suggestions")
            if isinstance(feedback.get("vocabulary_suggestions"), list)
            else [],
            "grammar_score": to_score10(self.grammar_score),
            "vocabulary_score": to_score10(self.vocabulary_score),
            "clarity_score": to_score10(self.clarity_score),
            "knowledge_score": to_score10(self.knowledge_score),
            "overall_score": to_score10(self.overall_score),
            "scores": {
                "grammar": to_score10(scores.get("grammar", self.grammar_score)),
                "vocabulary": to_score10(scores.get("vocabulary", self.vocabulary_score)),
                "clarity": to_score10(scores.get("clarity", self.clarity_score)),
                "spelling": to_score10(scores.get("spelling")),
                "relevance": to_score10(scores.get("relevance")),
                "knowledge": to_score10(scores.get("knowledge", self.knowledge_score)),
                "overall": to_score10(scores.get("overall", self.overall_score)),
            },
            "feedback": self.feedback,
            "draft_text": self.draft_text,
            "draft_updated_at": self.draft_updated_at.isoformat() if self.draft_updated_at else None,
            "used_ai_suggestion": self.used_ai_suggestion,
            "weak_area_tags": _json_list(self.weak_area_tags),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class Topic(db.Model):
    __tablename__ = "topics"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(20), nullable=False)  # 'speaking' | 'writing'
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(400), nullable=True)
    difficulty = db.Column(db.String(20), nullable=False, default="medium")

    def to_dict(self):
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "difficulty": self.difficulty,
        }


class GeneratedTopic(db.Model):
    __tablename__ = "generated_topics"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    practice_type = db.Column(db.String(20), nullable=False)
    mode = db.Column(db.String(30), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    expected_duration_seconds = db.Column(db.Integer, nullable=True)
    minimum_word_count = db.Column(db.Integer, nullable=True)
    maximum_word_count = db.Column(db.Integer, nullable=True)
    source = db.Column(db.String(20), nullable=False, default="groq")
    used_in_session = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "topic_id": self.public_id,
            "title": self.title,
            "description": self.description,
            "difficulty": self.difficulty,
            "practice_type": self.practice_type,
            "mode": self.mode,
            "expected_duration_seconds": self.expected_duration_seconds,
            "minimum_word_count": self.minimum_word_count,
            "maximum_word_count": self.maximum_word_count,
            "source": self.source,
        }


class PronunciationItem(db.Model):
    __tablename__ = "pronunciation_items"
    __table_args__ = (
        db.UniqueConstraint("user_id", "daily_date", "practice_mode", "difficulty", name="uq_pronunciation_daily_user_date_mode_difficulty"),
    )

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    practice_mode = db.Column(db.String(30), nullable=False, index=True)
    item_type = db.Column(db.String(20), nullable=False)
    text = db.Column(db.Text, nullable=False)
    meaning = db.Column(db.Text, nullable=True)
    example_sentence = db.Column(db.Text, nullable=True)
    syllables = db.Column(db.String(200), nullable=True)
    difficulty = db.Column(db.String(20), nullable=False, default="medium")
    expected_duration_seconds = db.Column(db.Integer, nullable=True)
    source = db.Column(db.String(20), nullable=False, default="groq")
    metadata_json = db.Column(db.Text, nullable=True)
    daily_date = db.Column(db.Date, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    attempts = db.relationship("PronunciationAttempt", backref="item", cascade="all, delete-orphan")

    def to_dict(self):
        metadata = _json_dict(self.metadata_json)
        if self.practice_mode == "daily":
            content = {
                "title": metadata.get("title") or self.meaning or "Daily Challenge",
                "description": metadata.get("description") or metadata.get("why_today"),
                "practice_lines": metadata.get("practice_lines")
                if isinstance(metadata.get("practice_lines"), list)
                else [line.strip() for line in (self.text or "").splitlines() if line.strip()],
                "instructions": metadata.get("instructions") if isinstance(metadata.get("instructions"), list) else [],
                "goal": metadata.get("goal") or metadata.get("speaking_goal"),
                "expected_duration_seconds": self.expected_duration_seconds,
            }
        elif self.practice_mode == "minimal_pairs":
            pair = metadata.get("pair") if isinstance(metadata.get("pair"), list) else []
            content = {
                "title": metadata.get("title") or self.text,
                "practice_text": self.text,
                "word_a": metadata.get("word_a") or (pair[0] if len(pair) > 0 else None),
                "word_b": metadata.get("word_b") or (pair[1] if len(pair) > 1 else None),
                "pair": pair,
                "sound_contrast": metadata.get("sound_contrast"),
                "interaction": metadata.get("interaction") or "sequential_production",
                "meaning": self.meaning,
                "expected_duration_seconds": self.expected_duration_seconds,
            }
        elif self.practice_mode == "sentence":
            content = {
                "title": metadata.get("title") or "Sentence Practice",
                "practice_text": self.text,
                "expected_duration_seconds": self.expected_duration_seconds,
            }
        else:
            syllables = metadata.get("syllables") if isinstance(metadata.get("syllables"), list) else None
            if not syllables and self.syllables:
                syllables = [part.strip() for part in self.syllables.replace("-", " ").split() if part.strip()]
            content = {
                "title": metadata.get("title") or self.text,
                "practice_text": self.text,
                "meaning": self.meaning,
                "example_sentence": self.example_sentence,
                "syllables": syllables,
                "expected_duration_seconds": self.expected_duration_seconds,
            }
        return {
            "item_id": self.public_id,
            "practice_mode": self.practice_mode,
            "item_type": self.item_type,
            "text": self.text,
            "meaning": self.meaning,
            "example_sentence": self.example_sentence,
            "syllables": self.syllables,
            "difficulty": self.difficulty,
            "expected_duration_seconds": self.expected_duration_seconds,
            "source": self.source,
            "metadata": metadata,
            "content": content,
            "daily_date": self.daily_date.isoformat() if self.daily_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PronunciationSession(db.Model):
    __tablename__ = "pronunciation_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    mode = db.Column(db.String(30), nullable=False)  # 'word' | 'sentence' | 'daily' | 'minimal_pairs'
    difficulty = db.Column(db.String(20), nullable=False, default="medium")
    total_questions = db.Column(db.Integer, nullable=False, default=5)
    questions_completed = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="in_progress")  # in_progress | completed
    average_score = db.Column(db.Float, nullable=True)
    summary_feedback = db.Column(db.Text, nullable=True)
    strengths_json = db.Column(db.Text, nullable=True)
    weaknesses_json = db.Column(db.Text, nullable=True)
    recommendation = db.Column(db.Text, nullable=True)
    next_practice_suggestion = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    attempts = db.relationship("PronunciationAttempt", backref="pronunciation_session", cascade="all, delete-orphan", foreign_keys="PronunciationAttempt.session_id", order_by="PronunciationAttempt.turn_number")

    def to_summary_dict(self):
        return {
            "id": self.id,
            "type": "pronunciation",
            "mode": self.mode,
            "difficulty": self.difficulty,
            "status": self.status,
            "total_questions": self.total_questions,
            "questions_completed": self.questions_completed,
            "overall_score": to_score10(self.average_score),
            "topic_title": f"{self.mode.capitalize()} Practice",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_detail_dict(self):
        data = self.to_summary_dict()
        data.update({
            "summary_feedback": self.summary_feedback,
            "strengths": _json_list(self.strengths_json),
            "areas_to_improve": _json_list(self.weaknesses_json),
            "recommendation": self.recommendation,
            "next_practice_suggestion": self.next_practice_suggestion,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "turns": [a.to_session_turn_dict() for a in self.attempts if a.status == "completed"],
        })
        return data


class PronunciationAttempt(db.Model):
    __tablename__ = "pronunciation_attempts"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("pronunciation_items.id"), nullable=False, index=True)
    # Session linkage — nullable for backward compatibility with standalone attempts
    session_id = db.Column(db.Integer, db.ForeignKey("pronunciation_sessions.id"), nullable=True, index=True)
    turn_number = db.Column(db.Integer, nullable=True)  # question number within session (1-based)
    attempt_number = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(20), nullable=False, default="started")
    sound_tags_json = db.Column(db.Text, nullable=True)
    effective_difficulty = db.Column(db.String(20), nullable=True)
    recognised_text = db.Column(db.Text, nullable=True)
    recognition_confidence = db.Column(db.Float, nullable=True)
    reference_locale = db.Column(db.String(20), nullable=True)
    duration_seconds = db.Column(db.Float, nullable=True)
    assessment_type = db.Column(db.String(60), nullable=False, default="speech_recognition_match")
    match_percentage = db.Column(db.Integer, nullable=True)
    word_accuracy_score = db.Column(db.Float, nullable=True)
    completeness_score = db.Column(db.Float, nullable=True)
    clarity_score = db.Column(db.Float, nullable=True)
    fluency_score = db.Column(db.Float, nullable=True)
    overall_score = db.Column(db.Float, nullable=True)
    comparison_json = db.Column(db.Text, nullable=True)
    feedback_json = db.Column(db.Text, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_summary_dict(self):
        return {
            "id": self.id,
            "attempt_id": self.public_id,
            "type": "pronunciation",
            "item_type": self.item.item_type if self.item else None,
            "practice_mode": self.item.practice_mode if self.item else None,
            "topic_title": self.item.text if self.item else "Pronunciation Practice",
            "difficulty": self.item.difficulty if self.item else None,
            "status": self.status,
            "match_percentage": self.match_percentage,
            "overall_score": to_score10(self.overall_score),
            "attempt_number": self.attempt_number,
            "session_id": self.session_id,
            "turn_number": self.turn_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def to_session_turn_dict(self):
        """Compact dict for use inside PronunciationSession.to_detail_dict() turns list."""
        comparison = _json_dict(self.comparison_json)
        feedback = _json_dict(self.feedback_json)
        return {
            "turn_number": self.turn_number,
            "reference_text": self.item.text if self.item else None,
            "recognised_text": self.recognised_text,
            "overall_score": to_score10(self.overall_score),
            "match_percentage": self.match_percentage,
            "scores": {
                "word_accuracy": to_score10(self.word_accuracy_score),
                "completeness": to_score10(self.completeness_score),
                "clarity": to_score10(self.clarity_score),
                "fluency": to_score10(self.fluency_score),
                "overall": to_score10(self.overall_score),
            },
            "feedback": feedback,
            "comparison": comparison,
            "minimal_pair_results": comparison.get("minimal_pair_results", []),
            "distinguishability": comparison.get("distinguishability"),
        }

    def to_detail_dict(self):
        comparison = _json_dict(self.comparison_json)
        feedback = _json_dict(self.feedback_json)
        data = self.to_summary_dict()
        data.update({
            "reference_text": self.item.text if self.item else None,
            "recognised_text": self.recognised_text,
            "recognition_confidence": self.recognition_confidence,
            "reference_locale": self.reference_locale,
            "duration_seconds": self.duration_seconds,
            "assessment_type": self.assessment_type,
            "scores": {
                "word_accuracy": to_score10(self.word_accuracy_score),
                "completeness": to_score10(self.completeness_score),
                "clarity": to_score10(self.clarity_score),
                "fluency": to_score10(self.fluency_score),
                "overall": to_score10(self.overall_score),
            },
            "comparison": comparison,
            "minimal_pair_results": comparison.get("minimal_pair_results", []),
            "distinguishability": comparison.get("distinguishability"),
            "word_results": comparison.get("word_results", []),
            "correct_words": comparison.get("correct_words", []),
            "missing_words": comparison.get("missing_words", []),
            "different_words": comparison.get("different_words", []),
            "extra_words": comparison.get("extra_words", []),
            "feedback": feedback,
        })
        return data


class DailyChallengeProgress(db.Model):
    __tablename__ = "daily_challenge_progress"
    __table_args__ = (
        db.UniqueConstraint("user_id", "challenge_date", "activity_type", name="uq_daily_challenge_progress_user_date_activity"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    challenge_date = db.Column(db.Date, nullable=False, index=True)
    activity_type = db.Column(db.String(80), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="not_started")
    source_session_id = db.Column(db.Integer, nullable=True)
    source_result_id = db.Column(db.Integer, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    xp_awarded = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DailyChallengeSummary(db.Model):
    __tablename__ = "daily_challenge_summary"
    __table_args__ = (
        db.UniqueConstraint("user_id", "challenge_date", name="uq_daily_challenge_summary_user_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    challenge_date = db.Column(db.Date, nullable=False, index=True)
    completed_count = db.Column(db.Integer, nullable=False, default=0)
    total_count = db.Column(db.Integer, nullable=False, default=3)
    all_completed = db.Column(db.Boolean, nullable=False, default=False)
    bonus_xp_awarded = db.Column(db.Integer, nullable=False, default=0)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LlmUsage(db.Model):
    """One row per LLM call, attributed to the verified DigiDARA user id
    (`X-DigiDARA-User-Id`, forwarded by the orchestrator gateway) that
    triggered it, mirroring agents/project_AI_Agent's identical table.
    groq_usage.log_groq_attempt deliberately only prints to the terminal
    ("does not store usage in the database... does not expose prompts,
    learner answers, API keys, JWTs, headers or model response text") — this
    table respects that same privacy boundary: only the model name, token
    counts, an operation label and the caller's platform user id are ever
    written here, nothing from the request/response bodies."""

    __tablename__ = "llm_usage"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(128), nullable=True, index=True)
    provider = db.Column(db.String(50))
    model_name = db.Column(db.String(100))
    prompt_tokens = db.Column(db.Integer, default=0)
    completion_tokens = db.Column(db.Integer, default=0)
    total_tokens = db.Column(db.Integer, default=0)
    request_type = db.Column(db.String(64), default="unspecified")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
