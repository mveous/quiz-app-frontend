import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import Question, QuestionOption, Quiz


class QuizRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, quiz: Quiz) -> Quiz:
        self._session.add(quiz)
        await self._session.flush()
        return quiz

    async def get_by_id(self, quiz_id: uuid.UUID) -> Quiz | None:
        result = await self._session.execute(select(Quiz).where(Quiz.id == quiz_id))
        return result.scalar_one_or_none()

    async def list_for_owner(self, owner_user_id: uuid.UUID, limit: int = 50) -> list[Quiz]:
        result = await self._session.execute(
            select(Quiz)
            .where(Quiz.owner_user_id == owner_user_id)
            .order_by(Quiz.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_questions(self, quiz_id: uuid.UUID) -> None:
        await self._session.execute(delete(Question).where(Question.quiz_id == quiz_id))

    async def list_questions(self, quiz_id: uuid.UUID) -> list[Question]:
        result = await self._session.execute(
            select(Question).where(Question.quiz_id == quiz_id).order_by(Question.order_index)
        )
        return list(result.scalars().all())

    async def get_question(self, question_id: uuid.UUID) -> Question | None:
        result = await self._session.execute(select(Question).where(Question.id == question_id))
        return result.scalar_one_or_none()

    async def list_options(self, question_id: uuid.UUID) -> list[QuestionOption]:
        result = await self._session.execute(
            select(QuestionOption)
            .where(QuestionOption.question_id == question_id)
            .order_by(QuestionOption.order_index)
        )
        return list(result.scalars().all())

    async def list_options_for_questions(
        self, question_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[QuestionOption]]:
        if not question_ids:
            return {}
        result = await self._session.execute(
            select(QuestionOption)
            .where(QuestionOption.question_id.in_(question_ids))
            .order_by(QuestionOption.order_index)
        )
        options_by_question: dict[uuid.UUID, list[QuestionOption]] = {}
        for option in result.scalars().all():
            options_by_question.setdefault(option.question_id, []).append(option)
        return options_by_question
