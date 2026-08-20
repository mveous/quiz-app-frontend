import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt import AttemptAnswer, QuizAttempt
from app.models.enums import AttemptStatus
from app.models.quiz import Quiz


class AttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, attempt: QuizAttempt) -> QuizAttempt:
        self._session.add(attempt)
        await self._session.flush()
        return attempt

    async def get_by_id(self, attempt_id: uuid.UUID) -> QuizAttempt | None:
        result = await self._session.execute(
            select(QuizAttempt).where(QuizAttempt.id == attempt_id)
        )
        return result.scalar_one_or_none()

    async def get_answer(
        self, attempt_id: uuid.UUID, question_id: uuid.UUID
    ) -> AttemptAnswer | None:
        result = await self._session.execute(
            select(AttemptAnswer).where(
                AttemptAnswer.attempt_id == attempt_id, AttemptAnswer.question_id == question_id
            )
        )
        return result.scalar_one_or_none()

    async def get_in_progress(self, quiz_id: uuid.UUID, user_id: uuid.UUID) -> QuizAttempt | None:
        result = await self._session.execute(
            select(QuizAttempt).where(
                QuizAttempt.quiz_id == quiz_id,
                QuizAttempt.user_id == user_id,
                QuizAttempt.status == AttemptStatus.IN_PROGRESS,
            )
        )
        return result.scalar_one_or_none()

    async def list_answers(self, attempt_id: uuid.UUID) -> list[AttemptAnswer]:
        result = await self._session.execute(
            select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt_id)
        )
        return list(result.scalars().all())

    async def list_submitted_for_user(
        self, user_id: uuid.UUID, limit: int = 20
    ) -> list[tuple[QuizAttempt, str]]:
        result = await self._session.execute(
            select(QuizAttempt, Quiz.title)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(QuizAttempt.user_id == user_id, QuizAttempt.status == AttemptStatus.SUBMITTED)
            .order_by(QuizAttempt.submitted_at.desc())
            .limit(limit)
        )
        return [(attempt, title) for attempt, title in result.all()]

    async def upsert_answer(
        self,
        attempt_id: uuid.UUID,
        question_id: uuid.UUID,
        response_text: str | None,
        selected_option_id: uuid.UUID | None,
    ) -> AttemptAnswer:
        answer = await self.get_answer(attempt_id, question_id)
        if answer is None:
            answer = AttemptAnswer(
                attempt_id=attempt_id,
                question_id=question_id,
                response_text=response_text,
                selected_option_id=selected_option_id,
            )
            self._session.add(answer)
        else:
            answer.response_text = response_text
            answer.selected_option_id = selected_option_id
        await self._session.flush()
        return answer
