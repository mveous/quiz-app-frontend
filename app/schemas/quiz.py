import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import Difficulty, QuestionType, QuizStatus


class SubjectOut(BaseModel):
    id: uuid.UUID
    name: str
    is_global: bool
    country_id: uuid.UUID | None

    model_config = ConfigDict(from_attributes=True)


class TopicOut(BaseModel):
    id: uuid.UUID
    subject_id: uuid.UUID
    name: str
    parent_topic_id: uuid.UUID | None

    model_config = ConfigDict(from_attributes=True)


class QuizGenerateRequest(BaseModel):
    subject_id: uuid.UUID | None = None
    topic_id: uuid.UUID | None = None
    # Also doubles as the quiz's display title when generating from a picked subject/topic.
    topic_text: str | None = Field(default=None, max_length=200)
    source_text: str | None = Field(default=None, max_length=8000)
    question_count: int = Field(default=5, ge=1, le=20)
    difficulty: Difficulty = Difficulty.MEDIUM
    question_types: list[QuestionType] = Field(default_factory=lambda: [QuestionType.MCQ])
    use_my_documents: bool = Field(default=True)
    use_web_search: bool = Field(default=True)

    @model_validator(mode="after")
    def _validate(self) -> "QuizGenerateRequest":
        if not any([self.subject_id, self.topic_id, self.topic_text, self.source_text]):
            raise ValueError(
                "Provide at least one of subject_id, topic_id, topic_text, or source_text"
            )
        if not self.question_types:
            raise ValueError("question_types must not be empty")
        return self


class QuestionOptionOut(BaseModel):
    id: uuid.UUID
    label: str
    text: str
    order_index: int

    model_config = ConfigDict(from_attributes=True)


class QuestionOut(BaseModel):
    id: uuid.UUID
    type: QuestionType
    prompt: str
    difficulty: Difficulty
    order_index: int
    marks: float
    options: list[QuestionOptionOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class QuizOut(BaseModel):
    id: uuid.UUID
    title: str
    status: QuizStatus
    subject_id: uuid.UUID | None
    topic_id: uuid.UUID | None
    question_count: int
    difficulty: Difficulty
    error_message: str | None
    created_at: datetime
    questions: list[QuestionOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
