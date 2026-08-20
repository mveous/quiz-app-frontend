import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationFailedError
from app.models.attempt import AttemptAnswer, QuizAttempt
from app.models.enums import AttemptStatus, QuizStatus
from app.models.user import User
from app.repositories.attempt_repository import AttemptRepository
from app.repositories.quiz_repository import QuizRepository
from app.schemas.attempt import AnswerSubmitRequest
from app.services.ai.evaluation_service import EvaluationService
from app.services.ai.factory import get_ai_provider


class AttemptService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._attempts = AttemptRepository(session)
        self._quizzes = QuizRepository(session)

    async def start_attempt(self, user: User, quiz_id: uuid.UUID) -> QuizAttempt:
        quiz = await self._quizzes.get_by_id(quiz_id)
        if quiz is None:
            raise NotFoundError("Quiz not found")
        if quiz.owner_user_id != user.id:
            raise ForbiddenError("You do not have access to this quiz")
        if quiz.status != QuizStatus.READY:
            raise ValidationFailedError("Quiz is not ready yet")

        # Idempotent: re-entering a quiz already in progress (e.g. a back-navigation
        # remount) must resume the same attempt rather than spawn a new blank one on
        # every call.
        attempt = await self._attempts.get_in_progress(quiz.id, user.id)
        if attempt is None:
            attempt = QuizAttempt(
                quiz_id=quiz.id,
                user_id=user.id,
                started_at=datetime.now(timezone.utc),
                status=AttemptStatus.IN_PROGRESS,
            )
            await self._attempts.create(attempt)
            await self._session.commit()

        attempt.answers = await self._attempts.list_answers(attempt.id)
        return attempt

    async def submit_answer(
        self, user: User, attempt_id: uuid.UUID, data: AnswerSubmitRequest
    ) -> AttemptAnswer:
        attempt = await self._get_owned_attempt(user, attempt_id)
        if attempt.status != AttemptStatus.IN_PROGRESS:
            raise ValidationFailedError("Attempt has already been submitted")

        question = await self._quizzes.get_question(data.question_id)
        if question is None or question.quiz_id != attempt.quiz_id:
            raise ValidationFailedError("Question does not belong to this attempt's quiz")

        answer = await self._attempts.upsert_answer(
            attempt.id, data.question_id, data.response_text, data.selected_option_id
        )
        await self._session.commit()
        return answer

    async def submit_attempt(self, user: User, attempt_id: uuid.UUID) -> QuizAttempt:
        attempt = await self._get_owned_attempt(user, attempt_id)
        if attempt.status != AttemptStatus.IN_PROGRESS:
            raise ValidationFailedError("Attempt has already been submitted")

        questions = await self._quizzes.list_questions(attempt.quiz_id)
        answers_by_question = {a.question_id: a for a in await self._attempts.list_answers(attempt.id)}

        evaluator = EvaluationService(self._session, get_ai_provider())
        total_marks = 0.0
        score = 0.0
        for question in questions:
            total_marks += float(question.marks)
            answer = answers_by_question.get(question.id)
            if answer is None:
                # Unanswered questions are still graded (as incorrect) so the report is complete.
                answer = await self._attempts.upsert_answer(attempt.id, question.id, None, None)
            await evaluator.evaluate_answer(question, answer)
            score += answer.marks_awarded or 0.0

        attempt.status = AttemptStatus.SUBMITTED
        attempt.submitted_at = datetime.now(timezone.utc)
        attempt.score = round(score, 2)
        attempt.total_marks = round(total_marks, 2)
        await self._session.commit()
        return attempt

    async def _get_owned_attempt(self, user: User, attempt_id: uuid.UUID) -> QuizAttempt:
        attempt = await self._attempts.get_by_id(attempt_id)
        if attempt is None:
            raise NotFoundError("Attempt not found")
        if attempt.user_id != user.id:
            raise ForbiddenError("You do not have access to this attempt")
        return attempt
