import re

from pydantic import ValidationError

from app.schemas.material import Quiz
from app.services import ai_service

MAX_CONTEXT_CHARS = 12_000
NUM_QUESTIONS = 5

QUIZ_SYSTEM = (
    f"You create multiple-choice quizzes from learning material. "
    f"Write {NUM_QUESTIONS} questions based ONLY on the material given by the user. "
    "Each question has exactly 4 distinct options and one correct answer that is "
    "copied exactly from the options, plus a short explanation. "
    "Return ONLY valid JSON, with no markdown fences and no extra text, in this shape: "
    '{"questions": [{"question": "...", "options": ["...", "...", "...", "..."], '
    '"correct_answer": "...", "explanation": "..."}]}'
)


def sample_text(text: str, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """For long texts take 4 evenly spaced slices so questions cover the whole document."""
    if len(text) <= max_chars:
        return text
    parts = 4
    size = max_chars // parts
    step = (len(text) - size) // (parts - 1)
    return "\n...\n".join(text[i * step : i * step + size] for i in range(parts))


def parse_quiz(raw: str) -> Quiz:
    """Parse and validate the model output. Raises ValueError if it is not a valid quiz."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    return Quiz.model_validate_json(cleaned)  # ValidationError is a ValueError


def generate_quiz(text: str) -> Quiz:
    context = sample_text(text)
    for _ in range(2):  # one retry if the model returns invalid JSON
        raw = ai_service.chat(QUIZ_SYSTEM, context)
        try:
            return parse_quiz(raw)
        except (ValueError, ValidationError):
            continue
    raise ai_service.AIServiceError("The AI returned an invalid quiz. Please try again.")
