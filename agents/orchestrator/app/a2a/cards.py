"""A2A Agent Cards for every registered agent, and for the hub itself.

A card is built from the live registry row (name, description, version) plus
the skill list below. A skill id is the agent action an A2A client puts in
its data part, so `{"action": "start_interview", ...}` sent to the Mock
Interview card's URL runs that action. Agents can serve more actions than a
card lists; the card names the ones that matter to another agent or client.
"""
from __future__ import annotations

from app.a2a.protocol import PROTOCOL_VERSION
from app.learner.levels import LEVELED_AGENTS

SUMMARY_SKILL = {
    "id": "get_student_summary",
    "name": "Student summary",
    "description": (
        "The learner's progress with this agent in the shared "
        "digidara.student_summary.v1 shape: score 0-100, activity count, last "
        "activity, strengths and gaps. Used by the readiness service."
    ),
    "tags": ["readiness", "progress"],
}

READINESS_AGENT = "readiness"

# Skills per registry agent name. Ids are real actions of that agent.
AGENT_SKILLS: dict[str, list[dict]] = {
    "aptitude_agent": [
        {"id": "create_test", "name": "Create aptitude test", "description": "Generate a timed aptitude test.", "tags": ["aptitude", "test"]},
        {"id": "results", "name": "Test results", "description": "Score and review of a finished test (payload.test_id).", "tags": ["aptitude"]},
        {"id": "analytics", "name": "Aptitude analytics", "description": "Topic-wise performance over time.", "tags": ["aptitude", "progress"]},
    ],
    "codeforge_agent": [
        {"id": "list_problems", "name": "List coding problems", "description": "Problems for a course or topic.", "tags": ["coding"]},
        {"id": "run_problem", "name": "Run solution", "description": "Run code against a problem's tests.", "tags": ["coding"]},
        {"id": "dashboard", "name": "Coding progress", "description": "Solved problems and course progress.", "tags": ["coding", "progress"]},
    ],
    "communication_agent": [
        {"id": "writing_start", "name": "Start writing practice", "description": "Begin a graded writing session.", "tags": ["communication", "writing"]},
        {"id": "speaking_start", "name": "Start speaking practice", "description": "Begin a graded speaking session.", "tags": ["communication", "speaking"]},
        {"id": "dashboard", "name": "Communication progress", "description": "Writing, speaking and pronunciation progress.", "tags": ["communication", "progress"]},
    ],
    "mock_interview_agent": [
        {"id": "start_interview", "name": "Start mock interview", "description": "Plan and begin an interview for a role and difficulty.", "tags": ["interview"]},
        {"id": "submit_answer", "name": "Answer a question", "description": "Submit an answer to the current question.", "tags": ["interview"]},
        {"id": "history", "name": "Interview history", "description": "Past interviews and their scores.", "tags": ["interview", "progress"]},
    ],
    "resume_builder_agent": [
        {"id": "generate_resume", "name": "Generate resume", "description": "Build a resume from the learner's details.", "tags": ["resume"]},
        {"id": "tailor_to_job", "name": "Tailor resume to a job", "description": "Rewrite a resume for a job description.", "tags": ["resume", "jobs"]},
        {"id": "analyze_job_description", "name": "Analyze job description", "description": "Skills and keywords a job asks for.", "tags": ["resume", "jobs"]},
    ],
    "capstone_project_agent": [
        {"id": "choose_topic", "name": "Choose capstone topic", "description": "Pick a project topic suited to the learner.", "tags": ["projects"]},
        {"id": "ask_project_question", "name": "Project mentor", "description": "Answer a question about the learner's project.", "tags": ["projects"]},
    ],
    "certificate_agent": [
        {"id": "start_exam", "name": "Start certification exam", "description": "Begin an AI certification exam.", "tags": ["certification"]},
        {"id": "get_my_certificates", "name": "My certificates", "description": "Certificates the learner has earned.", "tags": ["certification", "progress"]},
    ],
    "job_agent": [
        {"id": "get_feed", "name": "Job feed", "description": "Jobs matched to the learner's profile.", "tags": ["jobs"]},
        {"id": "chat", "name": "Job assistant", "description": "Ask about jobs and applications.", "tags": ["jobs"]},
    ],
}


def _security() -> dict:
    return {
        "securitySchemes": {
            "bearer": {
                "type": "http", "scheme": "bearer", "bearerFormat": "JWT",
                "description": "A DigiDARA login token. Agents calling on a learner's behalf sign the "
                               "request with the shared service secret instead (X-Agent-* headers).",
            },
        },
        "security": [{"bearer": []}],
    }


def agent_card(base_url: str, agent_name: str, description: str, version: str) -> dict:
    skills = [dict(skill) for skill in AGENT_SKILLS.get(agent_name, [])]
    skills.append(dict(SUMMARY_SKILL))
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "name": LEVELED_AGENTS.get(agent_name, agent_name),
        "description": description,
        "url": f"{base_url}/a2a/{agent_name}",
        "preferredTransport": "JSONRPC",
        "version": version,
        "provider": {"organization": "DigiDARA Technologies", "url": base_url},
        "capabilities": {"streaming": False, "pushNotifications": False, "stateTransitionHistory": False},
        "defaultInputModes": ["application/json", "text/plain"],
        "defaultOutputModes": ["application/json"],
        "skills": skills,
        **_security(),
    }


def readiness_card(base_url: str) -> dict:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "name": "Job Readiness",
        "description": "The learner's overall job readiness, combined from every agent's student summary.",
        "url": f"{base_url}/a2a/{READINESS_AGENT}",
        "preferredTransport": "JSONRPC",
        "version": "1.0.0",
        "provider": {"organization": "DigiDARA Technologies", "url": base_url},
        "capabilities": {"streaming": False, "pushNotifications": False, "stateTransitionHistory": False},
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": [
            {"id": "get_readiness", "name": "Job readiness", "description": "Overall score, band, per-area scores and levels.", "tags": ["readiness"]},
            {"id": "get_learner_profile", "name": "Learner profile", "description": "Target role, skills, degree and per-agent levels.", "tags": ["profile"]},
        ],
        **_security(),
    }


def hub_card(base_url: str, cards: list[dict]) -> dict:
    """The hub's own card at /.well-known/agent-card.json: one skill per
    reachable agent, each pointing at that agent's own card."""
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "name": "DigiDARA Agent Hub",
        "description": "Every DigiDARA agent, reachable over A2A. Each skill below is an agent with its own card.",
        "url": f"{base_url}/a2a",
        "preferredTransport": "JSONRPC",
        "version": "2.0.0",
        "provider": {"organization": "DigiDARA Technologies", "url": base_url},
        "capabilities": {"streaming": False, "pushNotifications": False, "stateTransitionHistory": False},
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": [
            {
                "id": card["url"].rsplit("/", 1)[-1],
                "name": card["name"],
                "description": card["description"],
                "tags": ["agent"],
                "examples": [f"{card['url']}/.well-known/agent-card.json"],
            }
            for card in cards
        ],
        **_security(),
    }
