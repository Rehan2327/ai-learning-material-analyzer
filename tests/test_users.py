from tests.conftest import PASSWORD


def test_register_user(client):
    response = client.post("/users", json={"email": "Bob@Example.com", "password": PASSWORD})
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "bob@example.com"
    assert "password" not in body and "hashed_password" not in body


def test_duplicate_user_rejected(client):
    payload = {"email": "bob@example.com", "password": PASSWORD}
    assert client.post("/users", json=payload).status_code == 201
    assert client.post("/users", json=payload).status_code == 409


def test_invalid_email_rejected(client):
    response = client.post("/users", json={"email": "not-an-email", "password": PASSWORD})
    assert response.status_code == 422


def test_short_password_rejected(client):
    response = client.post("/users", json={"email": "bob@example.com", "password": "short"})
    assert response.status_code == 422
