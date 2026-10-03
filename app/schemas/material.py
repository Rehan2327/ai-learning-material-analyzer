from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    created_at: datetime


class SummaryResponse(BaseModel):
    material_id: int
    used_ocr: bool
    cached: bool
    summary: str


class QuizQuestion(BaseModel):
    question: str = Field(min_length=1)
    options: list[str]
    correct_answer: str
    explanation: str

    @model_validator(mode="after")
    def check_options(self) -> "QuizQuestion":
        if len(self.options) != 4 or len(set(self.options)) != 4:
            raise ValueError("each question needs exactly 4 distinct options")
        if self.correct_answer not in self.options:
            raise ValueError("correct_answer must be one of the options")
        return self


class Quiz(BaseModel):
    questions: list[QuizQuestion] = Field(min_length=1)


class QuizResponse(Quiz):
    material_id: int
    used_ocr: bool
    cached: bool
