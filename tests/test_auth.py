from tests.conftest import PASSWORD, auth_headers


def test_login_returns_token(client):
    client.post("/users", json={"email": "bob@example.com", "password": PASSWORD})
    response = client.post("/auth/login", data={"username": "bob@example.com", "password": PASSWORD})
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_wrong_password(client):
    client.post("/users", json={"email": "bob@example.com", "password": PASSWORD})
    response = client.post("/auth/login", data={"username": "bob@example.com", "password": "WrongPass999"})
    assert response.status_code == 401


def test_login_unknown_user(client):
    response = client.post("/auth/login", data={"username": "ghost@example.com", "password": PASSWORD})
    assert response.status_code == 401


def test_protected_route_without_token(client):
    assert client.post("/materials/1/summary").status_code == 401


def test_protected_route_with_invalid_token(client):
    response = client.post("/materials/1/summary", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401


def test_protected_route_with_valid_token(client):
    # A valid token passes authentication; the material simply does not exist (404, not 401).
    response = client.post("/materials/999/summary", headers=auth_headers(client))
    assert response.status_code == 404
