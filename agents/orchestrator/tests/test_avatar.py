"""Profile pictures on the server, shown on leaderboards."""
import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.security import create_access_token
from app.learner import routes as learner_routes
from app.models import ReadinessSnapshot, User

JPEG = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xe0" + b"0" * 100).decode()


def auth(user_id="learner"):
    return {"authorization": "Bearer " + create_access_token(user_id)}


@pytest.fixture
def client(database):
    with database() as session:
        for user_id in ("learner", "other"):
            session.add(User(id=user_id, name=f"{user_id.title()} Person", email=f"{user_id}@example.test",
                             email_verified=True, token_balance=10, password_hash="x"))
        session.commit()
    app = FastAPI()
    app.include_router(learner_routes.router)
    with TestClient(app) as test_client:
        yield test_client


def test_a_saved_picture_comes_back_and_shows_on_the_leaderboard(client, database):
    from app.readiness import leaderboard

    assert client.get("/learner/avatar", headers=auth()).json() == {"image": None}
    assert client.put("/learner/avatar", headers=auth(), json={"image": JPEG, "thumb": JPEG}).status_code == 200
    assert client.get("/learner/avatar", headers=auth()).json()["image"] == JPEG
    with database() as session:
        session.add(ReadinessSnapshot(user_id="learner", overall=50, band="developing", areas={}, role_key=""))
        session.add(ReadinessSnapshot(user_id="other", overall=40, band="developing", areas={}, role_key=""))
        session.commit()
    leaderboard.clear_cache()
    entries = client.get("/learner/leaderboard", headers=auth("other")).json()["entries"]
    assert [(e["user_id"], e["avatar"]) for e in entries] == [("learner", JPEG), ("other", None)]
    assert client.delete("/learner/avatar", headers=auth()).status_code == 204
    assert client.get("/learner/avatar", headers=auth()).json() == {"image": None}


@pytest.mark.parametrize("image", [
    "https://example.com/me.jpg",                                                     # not a data URL
    "data:image/svg+xml;base64," + base64.b64encode(b"<svg onload=alert(1)>").decode(),  # SVG can carry script
    "data:image/jpeg;base64," + base64.b64encode(b"<html>not a jpeg</html>").decode(),   # wrong content
    "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff" + b"0" * 210_000).decode(),  # too large
], ids=["not-data-url", "svg", "fake-jpeg", "too-large"])
def test_only_small_real_pictures_are_kept(client, image):
    assert client.put("/learner/avatar", headers=auth(), json={"image": image, "thumb": JPEG}).status_code in (400, 422)
