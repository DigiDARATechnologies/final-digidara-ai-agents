"""Example agent — copy this whole folder, rename it, replace `invoke()`
with your own logic (call your LangGraph graph, an LLM, a plain function,
anything that returns a dict), and edit manifest.json to describe it.
Nothing else needs to change: agent_wrapper.py handles registering with the
orchestrator, heartbeating, and exposing /health + /invoke for you.

Run it:
    pip install -r requirements.txt
    copy .env.example .env
    uvicorn main:app --reload --port 8201
"""
from pathlib import Path

from agent_wrapper import create_agent_app


def invoke(payload: dict) -> dict:
    """Replace this with your agent's real logic, e.g.:

        from my_agent.graph import compiled_graph
        def invoke(payload: dict) -> dict:
            return compiled_graph.invoke(payload)
    """
    text = payload.get("text", "")
    return {"echoed": text, "length": len(text)}


app = create_agent_app(Path(__file__).parent / "manifest.json", invoke)
