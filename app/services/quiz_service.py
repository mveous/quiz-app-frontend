import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationFailedError
from app.models.enums import QuizSourceType, QuizStatus
from app.models.quiz import Quiz
from app.models.user import User
from app.repositories.quiz_repository import QuizRepository
from app.schemas.quiz import QuizGenerateRequest


class QuizService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._quizzes = QuizRepository(session)

    async def create_quiz(self, user: User, data: QuizGenerateRequest) -> Quiz:
        source_type = QuizSourceType.TEXT if data.source_text else QuizSourceType.TOPIC
        source_ref = data.source_text or data.topic_text
        title = (data.topic_text or (data.source_text or "")[:60]).strip() or "Practice Quiz"

        quiz = Quiz(
            owner_user_id=user.id,
            title=title,
            subject_id=data.subject_id,
            topic_id=data.topic_id,
            source_type=source_type,
            source_ref=source_ref,
            question_count=data.question_count,
            question_types=[t.value for t in data.question_types],
            difficulty=data.difficulty,
            status=QuizStatus.GENERATING,
            use_my_documents=data.use_my_documents,
            use_web_search=data.use_web_search,
        )
        await self._quizzes.create(quiz)
        await self._session.commit()

        celery_app.send_task("quizzes.generate", args=[str(quiz.id)])
        return quiz

    async def retry_quiz(self, user: User, quiz_id: uuid.UUID) -> Quiz:
        quiz = await self.get_quiz_for_user(user, quiz_id)
        if quiz.status != QuizStatus.FAILED:
            raise ValidationFailedError("Only a failed quiz can be retried")

        # Defensive: generation only persists questions after a fully valid payload,
        # so a failed quiz should have none, but clear any partial rows before
        # re-running so a retry can never end up with duplicate questions.
        await self._quizzes.delete_questions(quiz.id)
        quiz.status = QuizStatus.GENERATING
        quiz.error_message = None
        await self._session.commit()

        celery_app.send_task("quizzes.generate", args=[str(quiz.id)])
        return quiz

    async def list_quizzes_for_user(self, user: User) -> list[Quiz]:
        return await self._quizzes.list_for_owner(user.id)

    async def get_quiz_for_user(self, user: User, quiz_id: uuid.UUID) -> Quiz:
        quiz = await self._quizzes.get_by_id(quiz_id)
        if quiz is None:
            raise NotFoundError("Quiz not found")
        if quiz.owner_user_id != user.id:
            raise ForbiddenError("You do not have access to this quiz")
        return quiz

    async def get_quiz_with_questions(self, user: User, quiz_id: uuid.UUID) -> tuple[Quiz, list]:
        quiz = await self.get_quiz_for_user(user, quiz_id)
        questions = await self._quizzes.list_questions(quiz_id) if quiz.status == QuizStatus.READY else []
        options_by_question = await self._quizzes.list_options_for_questions(
            [q.id for q in questions]
        )
        for question in questions:
            question.options = options_by_question.get(question.id, [])
        return quiz, questions
