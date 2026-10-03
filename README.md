# AI Learning Material Analyzer

## Overview
A FastAPI backend where authenticated users upload PDF learning material and receive an AI-generated summary and a multiple-choice quiz. Scanned (image-only) PDFs are handled with OCR.

## Features
- User registration and JWT login (OAuth2 password flow)
- PDF upload with validation (extension, `%PDF` signature, size limit)
- Text extraction with automatic OCR **only for pages that have no text**
- Structured AI summary and validated JSON quiz
- Results cached in the database (no repeated OCR or AI calls)
- Users can only access their own materials
- Swagger UI with an Authorize button

## Architecture
A modular monolith. Routes handle HTTP only; `services/` hold the logic and do not depend on FastAPI (so the Colab notebook can reuse them).

```
Client -> FastAPI routes -> services (pdf, ocr, ai, quiz) -> SQLite
```

## Tech Stack
FastAPI, SQLAlchemy 2 + SQLite, PyJWT, Argon2 (pwdlib), PyMuPDF, Tesseract (pytesseract), Google Gemini via the OpenAI-compatible SDK, pytest.

## Project Structure
```
app/
  main.py            # app + router registration
  core/              # config (.env), security (hash + JWT), dependencies
  db/                # engine/session, models (User, Material)
  schemas/           # Pydantic request/response models
  api/routes/        # users.py, auth.py, materials.py
  services/          # pdf_service, ocr_service, ai_service, quiz_service
tests/               # pytest suite
notebooks/           # Colab demo of the PDF -> OCR -> summary -> quiz pipeline
```

## Prerequisites
- Python 3.10+
- Tesseract OCR binary
  - Linux / Codespaces: `sudo apt update && sudo apt install -y tesseract-ocr`
  - macOS: `brew install tesseract`
  - Windows: install from https://github.com/UB-Mannheim/tesseract/wiki and add it to PATH
- A free Gemini API key: https://aistudio.google.com/apikey

## Installation
```bash
git clone <your-repo-url>
cd ai-learning-material-analyzer
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then edit .env
```

## Environment Variables
| Variable | Description |
|---|---|
| `DATABASE_URL` | SQLAlchemy URL, default `sqlite:///./app.db` |
| `JWT_SECRET` | Secret used to sign tokens (required). Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_ALGORITHM` | Default `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime, default `60` |
| `AI_API_KEY` | LLM provider key (required for summary/quiz) |
| `AI_MODEL` | Default `gemini-3.8-flash` |
| `AI_BASE_URL` | OpenAI-compatible endpoint, default is Gemini's |

Secrets live only in `.env`, which is git-ignored.

## Running the Application
```bash
python run.py
# or: uvicorn app.main:app --reload
```
The API runs at http://localhost:8000.

## Swagger
Interactive docs: http://localhost:8000/docs (ReDoc: `/redoc`).
Screenshot: `docs/swagger.png`

## API Endpoints
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/users` | No | Create a user (201, 409 if the email exists) |
| POST | `/auth/login` | No | Log in, returns a JWT (401 on bad credentials) |
| POST | `/materials/upload` | Yes | Upload a PDF (413 too large, 415 not a PDF) |
| POST | `/materials/{id}/summary` | Yes | OCR if needed + AI summary |
| POST | `/materials/{id}/quiz` | Yes | AI multiple-choice quiz |

Both summary and quiz accept `?regenerate=true` to bypass the cache.

## Authentication Flow
1. `POST /users` stores the email and an Argon2 password hash.
2. `POST /auth/login` verifies the password and returns a signed JWT (`sub` = user id, `exp`).
3. The client sends `Authorization: Bearer <token>` on protected routes.
4. `get_current_user` validates the token and loads the user (401 if invalid or expired).
5. Material queries filter by `id` **and** `owner_id`; other users' materials return 404.

## PDF -> OCR -> Summary/Quiz Pipeline
1. Upload: validate extension, `%PDF` signature and size; save under a random UUID name.
2. On first summary/quiz request, extract embedded text page by page (PyMuPDF).
3. Pages with fewer than 25 characters are rendered at 200 DPI and sent to Tesseract (max 20 pages).
4. Text is cleaned and stored in the database (`extracted_text`, `used_ocr`).
5. Summary: one LLM call for short text; long text is split into chunks, summarised, then merged (max 6 chunks).
6. Quiz: the LLM must return JSON; it is validated with Pydantic (4 distinct options, answer must be one of them). Invalid output is retried once, then the API returns 502.
7. Results are cached in the database.

## Testing
```bash
pytest -v
```
Tests use an in-memory database and generate PDFs on the fly. Only the LLM network call (and Tesseract in the OCR tests) is replaced, so the tests run offline. Covered: registration, duplicates, login, invalid login, protected routes, upload, invalid files, ownership, missing material, OCR path, caching, quiz validation.

## Example API Usage
```bash
curl -X POST localhost:8000/users -H "Content-Type: application/json" \
  -d '{"email":"me@example.com","password":"StrongPass123"}'

TOKEN=$(curl -s -X POST localhost:8000/auth/login \
  -d "username=me@example.com&password=StrongPass123" | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -X POST localhost:8000/materials/upload -H "Authorization: Bearer $TOKEN" -F "file=@notes.pdf"
curl -X POST localhost:8000/materials/1/summary -H "Authorization: Bearer $TOKEN"
curl -X POST localhost:8000/materials/1/quiz -H "Authorization: Bearer $TOKEN"
```

## Security Notes
- Passwords are hashed with Argon2; no plaintext is stored.
- JWT secret and API key come from environment variables only.
- Uploads are renamed to random UUIDs, so user-supplied file names are never used as paths.
- Same error for unknown email and wrong password.
- Provider and internal errors are logged server-side and returned to clients as generic messages.

## Limitations
- Tables are created on startup (no migrations).
- Processing is synchronous, so very large scanned PDFs can take a while (OCR capped at 20 pages).
- The cache is per material; editing is not supported, only `?regenerate=true`.
- Tesseract works best on clear, English text.

## Future Improvements
- Alembic migrations and PostgreSQL
- Background jobs for large PDFs
- Refresh tokens and rate limiting
- Multi-language OCR and configurable quiz size
