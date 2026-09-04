"""Wires the 14 nodes into two LangGraph state machines.

**Main graph** (`compiled_graph`): eligibility → topics → requirements →
timer → submission guide. This is a genuinely stateful, resumable flow — a
student pauses for days between steps — so it's checkpointed, and the two
human-in-the-loop breakpoints (topic choice, timer confirmation) use
`interrupt_before`.

**Submission graph** (`submission_graph`): docx/zip ingestion through
scoring. This is NOT checkpointed and takes no `thread_id` — every submit or
resubmit is a fresh, independent `.invoke()` seeded with the context it needs
(chosen topic, requirements, submission guide) pulled from the main thread's
state. Earlier this ran as a continuation of the main graph, rewound past
`END` with `update_state(..., as_node=...)` on resubmission — that turned out
to be unreliable: LangGraph would resurface a stale cached write for the
re-run node instead of actually re-executing it (confirmed by pointing a
resubmission at a broken file and finding it re-reported the *previous*
attempt's error). A fresh, checkpoint-free invocation per attempt sidesteps
that whole class of replay bugs — there's nothing to rewind.
"""
from __future__ import annotations

import pymysql
from langgraph.checkpoint.mysql.pymysql import PyMySQLSaver
from langgraph.graph import END, StateGraph
from sqlalchemy.engine import make_url

from app import config
from app.graph import nodes
from app.graph.state import ProjectAgentState


def _eligibility_router(state: ProjectAgentState) -> str:
    return "topic_generator" if state.get("eligible") else "blocked_exit"


def _after_docx_ingest_router(state: ProjectAgentState) -> str:
    return "halt" if state.get("status") == "error" else "continue"


def _after_zip_ingest_router(state: ProjectAgentState) -> str:
    return "halt" if state.get("status") == "error" else "continue"


def _structure_gate_router(state: ProjectAgentState) -> str:
    return "continue" if nodes.structure_gate_passed(state) else "revise"


def build_main_graph():
    graph = StateGraph(ProjectAgentState)

    graph.add_node("eligibility_check", nodes.eligibility_check_node)
    graph.add_node("blocked_exit", nodes.blocked_exit_node)
    graph.add_node("topic_generator", nodes.topic_generator_node)
    graph.add_node("requirement_expansion", nodes.requirement_expansion_node)
    graph.add_node("timer_init", nodes.timer_init_node)
    graph.add_node("generate_submission_guide", nodes.submission_guide_node)

    graph.set_entry_point("eligibility_check")

    graph.add_conditional_edges(
        "eligibility_check",
        _eligibility_router,
        {"topic_generator": "topic_generator", "blocked_exit": "blocked_exit"},
    )
    graph.add_edge("blocked_exit", END)

    graph.add_edge("topic_generator", "requirement_expansion")  # [WAIT: topic choice] pauses here
    graph.add_edge("requirement_expansion", "timer_init")  # [WAIT: OK/start-timer] pauses here
    graph.add_edge("timer_init", "generate_submission_guide")
    graph.add_edge("generate_submission_guide", END)

    db_url = make_url(config.DATABASE_URL)
    conn = pymysql.connect(
        host=db_url.host,
        port=db_url.port or 3306,
        user=db_url.username,
        password=db_url.password or "",
        database=db_url.database,
        autocommit=True,  # required by PyMySQLSaver.setup() to persist its tables
    )
    # Guard against MySQL's default 8-hour idle-connection close, the same
    # class of issue app/db/database.py already handles for the main engine
    # via pool_pre_ping. This raw pymysql connection has no such protection
    # on its own, and a stale connection here surfaces as a misleading
    # "MySQL server has gone away" error the very next time this agent is
    # used after any idle period. Wrapping cursor() to ping-and-reconnect
    # first fixes it transparently for every future query.
    _raw_cursor = conn.cursor
    def _cursor_with_reconnect(*args, **kwargs):
        conn.ping(reconnect=True)
        return _raw_cursor(*args, **kwargs)
    conn.cursor = _cursor_with_reconnect

    checkpointer = PyMySQLSaver(conn)
    checkpointer.setup()  # idempotent — creates the checkpoint tables on first run

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["requirement_expansion", "timer_init"],
    )


def build_submission_graph():
    graph = StateGraph(ProjectAgentState)

    graph.add_node("docx_ingest", nodes.docx_ingest_node)
    graph.add_node("zip_ingest", nodes.zip_ingest_node)
    graph.add_node("structure_validation", nodes.structure_validation_node)
    graph.add_node("zip_structure_validation", nodes.zip_structure_validation_node)
    graph.add_node("request_revision", nodes.request_revision_node)
    graph.add_node("code_execution", nodes.code_execution_node)
    graph.add_node("verify_output", nodes.output_verification_node)
    graph.add_node("code_quality_scorer", nodes.code_quality_scorer_node)
    graph.add_node("score_aggregator", nodes.score_aggregator_node)
    graph.add_node("feedback_generator", nodes.feedback_generator_node)

    graph.set_entry_point("docx_ingest")

    graph.add_conditional_edges(
        "docx_ingest",
        _after_docx_ingest_router,
        {"continue": "zip_ingest", "halt": END},
    )
    graph.add_conditional_edges(
        "zip_ingest",
        _after_zip_ingest_router,
        {"continue": "structure_validation", "halt": END},
    )
    graph.add_edge("structure_validation", "zip_structure_validation")
    graph.add_conditional_edges(
        "zip_structure_validation",
        _structure_gate_router,
        {"continue": "code_execution", "revise": "request_revision"},
    )
    graph.add_edge("request_revision", END)

    graph.add_edge("code_execution", "verify_output")
    graph.add_edge("verify_output", "code_quality_scorer")
    graph.add_edge("code_quality_scorer", "score_aggregator")
    graph.add_edge("score_aggregator", "feedback_generator")
    graph.add_edge("feedback_generator", END)

    return graph.compile()  # no checkpointer — always runs start-to-finish in one call


# Single shared compiled graphs for the app's lifetime.
compiled_graph = build_main_graph()
submission_graph = build_submission_graph()
