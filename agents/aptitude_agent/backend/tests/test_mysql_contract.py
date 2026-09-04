def test_health_confirms_mysql(client):
    response=client.get("/health")
    assert response.status_code==200
    assert response.get_json()["database"]=="mysql"


def test_dashboard_uses_authenticated_student(client,auth_headers):
    response=client.get("/api/aptitude/dashboard",headers=auth_headers)
    assert response.status_code==200
    assert response.get_json()["tests_completed"]==0


def test_dashboard_rejects_missing_token(client):
    response=client.get("/api/aptitude/dashboard")
    assert response.status_code==401
    assert response.get_json()["code"]=="authentication_required"
