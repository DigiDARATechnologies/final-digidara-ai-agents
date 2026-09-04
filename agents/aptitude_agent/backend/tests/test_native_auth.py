from io import BytesIO
from backend.app.extensions import db
from backend.app.models import Student


def registration_payload(email="new@example.com"):
    return {"name":"New Learner","email":email,"password":"SecurePass123","course":"B.Tech","department":"Computer Science","year":"Year 1","institution":"AptiDARA College","batch":"2026"}


def test_register_login_logout_flow(client):
    registered=client.post("/api/aptitude/auth/register",json=registration_payload())
    assert registered.status_code==201
    token=registered.get_json()["token"];headers={"Authorization":f"Bearer {token}"}
    assert client.get("/api/aptitude/me",headers=headers).status_code==200
    login=client.post("/api/aptitude/auth/login",json={"email":"new@example.com","password":"SecurePass123"})
    assert login.status_code==200
    login_headers={"Authorization":f"Bearer {login.get_json()['token']}"}
    assert client.post("/api/aptitude/auth/logout",headers=login_headers).status_code==200
    assert client.get("/api/aptitude/me",headers=login_headers).status_code==401


def test_registration_rejects_duplicate_email(client):
    assert client.post("/api/aptitude/auth/register",json=registration_payload()).status_code==201
    duplicate=client.post("/api/aptitude/auth/register",json=registration_payload())
    assert duplicate.status_code==409
    assert duplicate.get_json()["code"]=="email_exists"


def test_login_rejects_wrong_password(client):
    client.post("/api/aptitude/auth/register",json=registration_payload())
    response=client.post("/api/aptitude/auth/login",json={"email":"new@example.com","password":"wrong-password"})
    assert response.status_code==401
    assert response.get_json()["code"]=="invalid_credentials"


def test_profile_photo_upload_persists_and_can_be_removed(client,auth_headers):
    png=(b"\x89PNG\r\n\x1a\n"+b"test-profile-photo")
    uploaded=client.put(
        "/api/aptitude/me/photo",
        headers=auth_headers,
        data={"photo":(BytesIO(png),"avatar.png")},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code==200
    photo_url=uploaded.get_json()["photo_url"]
    assert photo_url.startswith("/api/aptitude/me/photo?v=")

    refreshed=client.get("/api/aptitude/me",headers=auth_headers)
    assert refreshed.status_code==200
    assert refreshed.get_json()["photo_url"]==photo_url
    displayed=client.get(photo_url,headers=auth_headers)
    assert displayed.status_code==200
    assert displayed.mimetype=="image/png"
    assert displayed.data==png

    removed=client.delete("/api/aptitude/me/photo",headers=auth_headers)
    assert removed.status_code==200
    assert removed.get_json()["photo_url"] is None
    assert client.get("/api/aptitude/me",headers=auth_headers).get_json()["photo_url"] is None
    assert client.get("/api/aptitude/me/photo",headers=auth_headers).status_code==404


def test_single_user_identity_survives_email_edit(client,app,monkeypatch):
    learner_id="stable-local-learner"
    with app.app_context():
        db.session.add(Student(id=learner_id,name="Kiruthika",email="edited@example.com"))
        db.session.commit()
    monkeypatch.setitem(app.config,"SINGLE_USER_MODE",True)
    monkeypatch.setitem(app.config,"LOCAL_USER_ID",learner_id)
    monkeypatch.setitem(app.config,"LOCAL_USER_EMAIL","old@example.com")
    response=client.get("/api/aptitude/me")
    assert response.status_code==200
    assert response.get_json()["id"]==learner_id
    assert response.get_json()["email"]=="edited@example.com"
