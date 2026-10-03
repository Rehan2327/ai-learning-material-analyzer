import json

from app.core.config import settings
from app.services import ocr_service
from tests.conftest import auth_headers, make_pdf, upload_pdf


def test_upload_pdf(client):
    headers = auth_headers(client)
    files = {"file": ("notes.pdf", make_pdf(), "application/pdf")}
    response = client.post("/materials/upload", files=files, headers=headers)
    assert response.status_code == 201
    assert response.json()["filename"] == "notes.pdf"


def test_upload_requires_login(client):
    files = {"file": ("notes.pdf", make_pdf(), "application/pdf")}
    assert client.post("/materials/upload", files=files).status_code == 401


def test_upload_rejects_non_pdf_extension(client):
    files = {"file": ("notes.txt", b"hello", "text/plain")}
    response = client.post("/materials/upload", files=files, headers=auth_headers(client))
    assert response.status_code == 415


def test_upload_rejects_fake_pdf(client):
    files = {"file": ("fake.pdf", b"this is not a pdf", "application/pdf")}
    response = client.post("/materials/upload", files=files, headers=auth_headers(client))
    assert response.status_code == 415


def test_upload_rejects_too_large_file(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    files = {"file": ("notes.pdf", make_pdf(), "application/pdf")}
    response = client.post("/materials/upload", files=files, headers=auth_headers(client))
    assert response.status_code == 413


def test_summary_and_caching(client, ai_calls):
    headers = auth_headers(client)
    material_id = upload_pdf(client, headers)

    first = client.post(f"/materials/{material_id}/summary", headers=headers)
    assert first.status_code == 200
    assert first.json()["cached"] is False
    assert first.json()["used_ocr"] is False  # text PDF: OCR must not run
    assert "Overview" in first.json()["summary"]

    second = client.post(f"/materials/{material_id}/summary", headers=headers)
    assert second.json()["cached"] is True
    assert len(ai_calls) == 1  # second request did not call the AI again


def test_quiz_is_valid_and_structured(client, ai_calls):
    headers = auth_headers(client)
    material_id = upload_pdf(client, headers)
    response = client.post(f"/materials/{material_id}/quiz", headers=headers)
    assert response.status_code == 200
    question = response.json()["questions"][0]
    assert len(question["options"]) == 4
    assert question["correct_answer"] in question["options"]


def test_quiz_invalid_ai_output_returns_502(client, monkeypatch):
    from app.services import ai_service

    monkeypatch.setattr(ai_service, "chat", lambda system, user: "this is not json")
    headers = auth_headers(client)
    material_id = upload_pdf(client, headers)
    response = client.post(f"/materials/{material_id}/quiz", headers=headers)
    assert response.status_code == 502


def test_quiz_rejects_answer_not_in_options(client, monkeypatch):
    from app.services import ai_service

    bad_quiz = {"questions": [{"question": "Q?", "options": ["a", "b", "c", "d"],
                               "correct_answer": "z", "explanation": "x"}]}
    monkeypatch.setattr(ai_service, "chat", lambda system, user: json.dumps(bad_quiz))
    headers = auth_headers(client)
    material_id = upload_pdf(client, headers)
    assert client.post(f"/materials/{material_id}/quiz", headers=headers).status_code == 502


def test_scanned_pdf_uses_ocr(client, ai_calls, monkeypatch):
    ocr_text = "Text recovered by OCR from a scanned page of learning material."
    monkeypatch.setattr(ocr_service, "ocr_page", lambda page: ocr_text)
    headers = auth_headers(client)
    material_id = upload_pdf(client, headers, content=make_pdf(text=None))
    response = client.post(f"/materials/{material_id}/summary", headers=headers)
    assert response.status_code == 200
    assert response.json()["used_ocr"] is True


def test_pdf_with_no_readable_text_returns_422(client, ai_calls, monkeypatch):
    monkeypatch.setattr(ocr_service, "ocr_page", lambda page: "")
    headers = auth_headers(client)
    material_id = upload_pdf(client, headers, content=make_pdf(text=None))
    response = client.post(f"/materials/{material_id}/summary", headers=headers)
    assert response.status_code == 422


def test_corrupted_pdf_returns_422(client, ai_calls):
    headers = auth_headers(client)
    material_id = upload_pdf(client, headers, content=b"%PDF-1.4 broken garbage content")
    response = client.post(f"/materials/{material_id}/summary", headers=headers)
    assert response.status_code == 422


def test_cannot_access_another_users_material(client, ai_calls):
    owner = auth_headers(client, "owner@example.com")
    intruder = auth_headers(client, "intruder@example.com")
    material_id = upload_pdf(client, owner)
    assert client.post(f"/materials/{material_id}/summary", headers=intruder).status_code == 404
    assert client.post(f"/materials/{material_id}/quiz", headers=intruder).status_code == 404


def test_missing_material_returns_404(client, ai_calls):
    headers = auth_headers(client)
    assert client.post("/materials/12345/summary", headers=headers).status_code == 404
    assert client.post("/materials/12345/quiz", headers=headers).status_code == 404
