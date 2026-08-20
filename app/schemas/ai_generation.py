from pydantic import BaseModel

from app.models.enums import Difficulty, QuestionType


class GeneratedOption(BaseModel):
    label: str
    text: str
    is_correct: bool


class GeneratedQuestion(BaseModel):
    type: QuestionType
    prompt: str
    difficulty: Difficulty
    explanation: str
    options: list[GeneratedOption] | None = None
    correct_answer_text: str | None = None
