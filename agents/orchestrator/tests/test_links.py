"""Links Boss makes on request (a chat, private or public; a certificate for
5 minutes, owner only), and Boss's own turns charged as points."""
from datetime import datetime

from app.links import routes as link_routes
from app.links import service as links_service
from app.llm import client as llm_client

from test_assist import _events, _mount
from test_phase2 import auth
from test_phase2_memory_voice import api  # noqa: F401  (fixture)


def _setup(api):  # noqa: F811
    from app import db
    from app.models import Conversation, ConversationMessage, User

    _mount(api)
    api.app.include_router(link_routes.router)
    session = db.get_session()
    session.add(User(id="friend", name="Friend", email="friend@example.test", email_verified=True,
                     token_balance=100000, password_hash="x"))
    session.flush()
    now = datetime.utcnow()
    session.add(Conversation(id="chat-mine-1", user_id="learner", agent_id="aptitude", title="Aptitude practice",
                             created_at=now, updated_at=now, updated_at_ms=1_760_000_000_000))
    session.flush()
    session.add(ConversationMessage(conversation_id="chat-mine-1", user_id="learner", position=0, role="user",
                                    content="Start a test", display_time="10:00"))
    session.commit()
    session.close()


def _reply(monkeypatch, *replies, tokens=0):
    pending = iter(replies)

    def fake_stream(messages, max_tokens=600, usage=None):
        if usage is not None and tokens:
            usage["tokens"] = tokens
        yield from [next(pending)]

    monkeypatch.setattr(llm_client, "stream_plain", fake_stream)


def test_a_private_chat_link_opens_only_for_its_owner_and_a_public_one_for_any_account(api, monkeypatch):  # noqa: F811
    _setup(api)
    _reply(monkeypatch, "Here is your private link to Aptitude practice. [[share:chat-mine-1:private]]",
           "Here is a public link. [[share:chat-mine-1:public]]", "Sure. [[share:chat-theirs:public]]")
    events = _events(api.post("/chat/assist/stream", headers=auth(), json={"message": "only for me"}))
    link = next(e["action"] for e in events if "action" in e)
    assert link["type"] == "link" and link["kind"] == "chat" and link["mode"] == "private"
    assert link["path"].startswith("/shared/chat/") and "chat-mine-1" not in link["path"]
    token = link["path"].rsplit("/", 1)[-1]
    mine = api.get(f"/links/chat/{token}", headers=auth())
    assert mine.status_code == 200 and mine.json()["is_owner"] and mine.json()["messages"][0]["text"] == "Start a test"
    assert api.get(f"/links/chat/{token}", headers=auth("friend")).status_code == 403

    events = _events(api.post("/chat/assist/stream", headers=auth(), json={"message": "public please"}))
    public = next(e["action"] for e in events if "action" in e)
    shared = api.get(f"/links/chat/{public['path'].rsplit('/', 1)[-1]}", headers=auth("friend"))
    assert shared.status_code == 200 and not shared.json()["is_owner"] and shared.json()["chat_id"] is None
    assert shared.json()["owner_name"] == "Learner"
    assert api.get(f"/links/chat/{token}").status_code == 401
    # A chat that is not the learner's own never gets a link.
    events = _events(api.post("/chat/assist/stream", headers=auth(), json={"message": "share it"}))
    assert not any("action" in e for e in events)


def test_a_certificate_link_lasts_five_minutes_and_only_its_owner_can_download(api, monkeypatch):  # noqa: F811
    _setup(api)
    looked_up = []

    def fake_certificates(user):
        looked_up.append(user.id)
        return [{"id": "7", "topic": "Python Basics", "certificate_number": "DD-7"}]

    monkeypatch.setattr(links_service, "own_certificates", fake_certificates)
    monkeypatch.setattr(links_service, "download_certificate", lambda user, cert_id: (b"%PDF-1.4 " + cert_id.encode(), "certificate_DD-7.pdf"))
    _reply(monkeypatch, "Here is your Python Basics certificate. [[certificate:7]]", "Sure. [[certificate:99]]", "Hello!")
    events = _events(api.post("/chat/assist/stream", headers=auth(), json={"message": "give me my certificate link"}))
    assert looked_up == ["learner"]
    link = next(e["action"] for e in events if "action" in e)
    assert link["kind"] == "certificate" and link["title"] == "Python Basics" and link["expires_in"] == 300
    token = link["path"].rsplit("/", 1)[-1]
    assert api.get(f"/links/certificate/{token}", headers=auth()).json()["can_download"] is True
    pdf = api.post(f"/links/certificate/{token}/download", headers=auth())
    assert pdf.status_code == 200 and pdf.content == b"%PDF-1.4 7" and pdf.headers["content-type"] == "application/pdf"
    other = api.post(f"/links/certificate/{token}/download", headers=auth("friend"))
    assert other.status_code == 403 and "owner" in other.json()["detail"]
    # Not one of the learner's certificates: no link.
    events = _events(api.post("/chat/assist/stream", headers=auth(), json={"message": "certificate 99 link"}))
    assert not any("action" in e for e in events)
    # Certificates are only looked up when the question is about them.
    api.post("/chat/assist/stream", headers=auth(), json={"message": "hello"})
    assert looked_up == ["learner", "learner"]

    real_time = links_service.time.time
    monkeypatch.setattr(links_service.time, "time", lambda: real_time() - 301)
    stale = links_service.create_certificate_link("learner", "7")["path"].rsplit("/", 1)[-1]
    monkeypatch.setattr(links_service.time, "time", real_time)
    expired = api.post(f"/links/certificate/{stale}/download", headers=auth())
    assert expired.status_code == 410 and "expired" in expired.json()["detail"]


def test_boss_turns_use_the_learners_points_and_stop_when_they_run_out(api, monkeypatch):  # noqa: F811
    from app import db
    from app.models import TokenUsageEvent, User

    _setup(api)
    _reply(monkeypatch, "Sure.", tokens=1234)
    assert _events(api.post("/chat/assist/stream", headers=auth(), json={"message": "help"}))[-1]["reply"] == "Sure."
    session = db.get_session()
    assert session.get(User, "learner").token_balance == 100000 - 1234
    event = session.query(TokenUsageEvent).filter_by(user_id="learner").one()
    assert (event.agent_name, event.action, event.tokens) == ("boss", "assist", 1234)
    session.get(User, "learner").token_balance = 0
    session.commit()
    session.close()
    refused = api.post("/chat/assist/stream", headers=auth(), json={"message": "help"})
    assert refused.status_code == 402 and "points" in refused.json()["detail"]
    assert api.post("/chat/route/stream", headers=auth(), json={"message": "hi", "history": []}).status_code == 402


def test_an_unreported_usage_is_estimated_so_a_call_is_never_free():
    usage = {}
    llm_client.record_usage(usage, None, [{"role": "user", "content": "x" * 400}], "y" * 400)
    assert usage["tokens"] == 200
    llm_client.record_usage(usage, type("U", (), {"total_tokens": 50})(), [], "")
    assert usage["tokens"] == 250
