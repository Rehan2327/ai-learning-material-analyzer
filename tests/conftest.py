import json
import os

os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-use-0123456789")
os.environ.setdefault("AI_API_KEY", "test-key")

import fitz  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.dependencies import get_db  # noqa: E402
from app.db.database import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.services import ai_service  # noqa: E402

PASSWORD = "StrongPass123"
SAMPLE_TEXT = (
    "Photosynthesis is the process plants use to convert sunlight, water and carbon "
    "dioxide into glucose and oxygen inside their chloroplasts."
)
FAKE_QUIZ = {
    "questions": [
        {
            "question": "What do plants convert sunlight into?",
            "options": ["Glucose", "Metal", "Plastic", "Sand"],
            "correct_answer": "Glucose",
            "explanation": "Photosynthesis produces glucose.",
        }
    ]
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient backed by a throw-away in-memory database and temp upload folder."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def ai_calls(monkeypatch):
    """Replace only the LLM network call; returns the list of calls made."""
    calls: list[str] = []

    def fake_chat(system: str, user: str) -> str:
        calls.append(system)
        if "JSON" in system:
            return json.dumps(FAKE_QUIZ)
        return "## Overview\nPlants make food from light."

    monkeypatch.setattr(ai_service, "chat", fake_chat)
    return calls


def auth_headers(client: TestClient, email: str = "alice@example.com") -> dict:
    client.post("/users", json={"email": email, "password": PASSWORD})
    response = client.post("/auth/login", data={"username": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def make_pdf(text: str | None = SAMPLE_TEXT) -> bytes:
    """Build a real PDF in memory. text=None gives a blank (image-less) page."""
    doc = fitz.open()
    page = doc.new_page()
    if text:
        page.insert_textbox(fitz.Rect(50, 50, 500, 300), text)
    return doc.tobytes()


def upload_pdf(client: TestClient, headers: dict, content: bytes | None = None) -> int:
    files = {"file": ("notes.pdf", content or make_pdf(), "application/pdf")}
    response = client.post("/materials/upload", files=files, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]
