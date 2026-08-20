import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import BloomLevel, Difficulty, QuestionType, QuizSourceType, QuizStatus


def _enum(python_enum, name: str):
    return Enum(python_enum, name=name, values_callable=lambda e: [m.value for m in e])


class Quiz(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quizzes"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True
    )
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
    source_type: Mapped[QuizSourceType] = mapped_column(
        _enum(QuizSourceType, "quiz_source_type"), nullable=False
    )
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    question_types: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    difficulty: Mapped[Difficulty] = mapped_column(_enum(Difficulty, "difficulty"), nullable=False)
    status: Mapped[QuizStatus] = mapped_column(
        _enum(QuizStatus, "quiz_status"), nullable=False, default=QuizStatus.GENERATING
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    use_my_documents: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    use_web_search: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Question(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "questions"

    quiz_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[QuestionType] = mapped_column(_enum(QuestionType, "question_type"), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[Difficulty] = mapped_column(_enum(Difficulty, "question_difficulty"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    marks: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=1)
    bloom_level: Mapped[BloomLevel | None] = mapped_column(_enum(BloomLevel, "bloom_level"), nullable=True)


class QuestionOption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_options"

    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(10), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
