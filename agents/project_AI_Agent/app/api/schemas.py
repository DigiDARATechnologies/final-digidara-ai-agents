from pydantic import BaseModel, Field


class FreeTopicRequest(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    # Optional -- there is no certificate/enrollment gate, so nothing else
    # requires a phone on file; the student is keyed on email instead. A
    # logged-in account with no phone (e.g. Google sign-in) still works.
    phone: str = ""
    course_name: str = Field(min_length=1)  # doubles as the free-text language/role/topic
    difficulty: str = Field(default="easy", pattern="^(easy|medium|hard)$")


class TopicClarifyRequest(BaseModel):
    description: str = Field(min_length=1)


class TopicClarifyResponse(BaseModel):
    ready: bool
    clarifying_question: str | None = None


class EligibilityCheckResponse(BaseModel):
    thread_id: str
    eligible: bool
    eligibility_reason: str
    topic_options: list[dict] | None = None


class TopicChooseRequest(BaseModel):
    thread_id: str
    topic_id: str  # "A" or "B", matching topic_options[].id


class TopicChooseResponse(BaseModel):
    thread_id: str
    chosen_topic: dict
    requirements: dict


class TimerConfirmRequest(BaseModel):
    thread_id: str


class TimerConfirmResponse(BaseModel):
    thread_id: str
    deadline_at: str
    submission_guide: dict
    # Plain-language "about this project" doc -- see app/graph/report.py.
    # Also downloadable as a raw .md file via GET /api/assignment/{thread_id}/about.md
    about_markdown: str | None = None


class VivaQuestionOut(BaseModel):
    id: int
    question: str


class VivaAnswerRequest(BaseModel):
    submission_id: str
    question_id: int
    answer: str


class SubmissionResultResponse(BaseModel):
    thread_id: str
    status: str
    submission_id: str | None = None
    revision_notes: str | None = None
    # Real syntax errors found in the submitted code (see
    # app/ingestion/syntax_check.py), one dict each: path, language, line,
    # column, message, source_line. Present only when the submission was sent
    # back because of them.
    syntax_errors: list[dict] | None = None
    final_score: float | None = None
    passed: bool | None = None
    feedback: str | None = None
    # Already computed by ScoreAggregatorNode/CodeQualityScorerNode and
    # persisted, just not previously returned to the client — the per-axis
    # breakdown behind the single final_score number.
    score_reasoning: str | None = None
    code_quality_score: dict | None = None
    # Full plain-language review report -- see app/graph/report.py. Also
    # downloadable as a raw .md file via GET /api/submission/{submission_id}/review.md
    review_markdown: str | None = None
    # Post-grading viva (oral defense) -- see app/viva.py.
    viva_question: VivaQuestionOut | None = None
    viva_progress: str | None = None
    viva_score: float | None = None
    viva_passed: bool | None = None
    # The viva is reported as Good / Average / Bad, never as a mark. Up to
    # `viva_attempts_total` attempts, each with a fresh set of questions.
    viva_rating: str | None = None
    viva_attempt: int | None = None
    viva_attempts_left: int | None = None
    viva_attempts_total: int | None = None


class StatusResponse(BaseModel):
    thread_id: str
    status: str | None = None
    deadline_at: str | None = None
    next_step: str

    # Full resumable state — lets the frontend rehydrate after a page reload
    # (or a return visit days later, mid-7-day-window) without re-deriving it.
    eligible: bool | None = None
    eligibility_reason: str | None = None
    topic_options: list[dict] | None = None
    chosen_topic: dict | None = None
    requirements: dict | None = None
    submission_guide: dict | None = None
    about_markdown: str | None = None
    final_score: float | None = None
    passed: bool | None = None
    feedback: str | None = None
    revision_notes: str | None = None
    score_reasoning: str | None = None
    code_quality_score: dict | None = None
    review_markdown: str | None = None


class StructureScreenshotObservation(BaseModel):
    path: str
    found_in_screenshot: bool
    guidance: str


class StructureScreenshotResponse(BaseModel):
    observations: list[StructureScreenshotObservation]
    summary: str


class QAAskResponse(BaseModel):
    answer: str
    # Which tools the agent actually called to answer -- transparency into
    # what grounded the response (e.g. ["get_project_brief", "read_submitted_file"]).
    tools_used: list[str]


class ConfigOut(BaseModel):
    pass_threshold: int
    submission_window_days: int
    max_upload_mb: int


class UsageSummaryResponse(BaseModel):
    agent_name: str
    total_requests: int
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    by_request_type: dict[str, int]
