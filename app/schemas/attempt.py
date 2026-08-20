import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AttemptStatus


class AnswerSubmitRequest(BaseModel):
    question_id: uuid.UUID
    response_text: str | None = Field(default=None, max_length=5000)
    selected_option_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _require_a_response(self) -> "AnswerSubmitRequest":
        if self.response_text is None and self.selected_option_id is None:
            raise ValueError("Provide either response_text or selected_option_id")
        return self


class AnswerOut(BaseModel):
    id: uuid.UUID
    question_id: uuid.UUID
    selected_option_id: uuid.UUID | None = None
    response_text: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AttemptOut(BaseModel):
    id: uuid.UUID
    quiz_id: uuid.UUID
    status: AttemptStatus
    started_at: datetime
    submitted_at: datetime | None
    score: float | None
    total_marks: float | None
    answers: list[AnswerOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class QuestionReportOut(BaseModel):
    question_id: uuid.UUID
    prompt: str
    type: str
    difficulty: str
    bloom_level: str | None
    your_answer: str | None
    is_correct: bool | None
    marks_awarded: float | None
    marks: float
    explanation: str | None
    ai_feedback: str | None


class BloomBreakdownOut(BaseModel):
    """Accuracy (0-100) per Bloom's level present in this attempt; a level absent
    from the quiz is omitted rather than reported as 0%."""

    remember: float | None = None
    understand: float | None = None
    apply: float | None = None
    analyze: float | None = None
    evaluate: float | None = None
    create: float | None = None


class TrendPointOut(BaseModel):
    attempt_id: uuid.UUID
    quiz_title: str
    submitted_at: datetime
    accuracy: float


class TrendOut(BaseModel):
    previous_attempt_accuracy: float | None
    average_recent_accuracy: float | None
    delta_vs_previous: float | None
    delta_vs_average: float | None
    recent_points: list[TrendPointOut]


class AttemptReportOut(BaseModel):
    id: uuid.UUID
    quiz_id: uuid.UUID
    status: AttemptStatus
    score: float
    total_marks: float
    accuracy: float
    time_taken_seconds: int | None
    questions: list[QuestionReportOut]
    strong_difficulty_bands: list[str]
    weak_difficulty_bands: list[str]
    bloom_breakdown: BloomBreakdownOut
    trend: TrendOut


class AttemptSummaryOut(BaseModel):
    id: uuid.UUID
    quiz_id: uuid.UUID
    quiz_title: str
    submitted_at: datetime
    score: float
    total_marks: float
    accuracy: float
