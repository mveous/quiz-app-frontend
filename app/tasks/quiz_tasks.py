import asyncio
import logging
import uuid

from app.core.celery_app import celery_app
from app.database.session import TaskSessionLocal
from app.models.enums import QuizStatus
from app.models.quiz import Quiz
from app.services.ai.factory import get_ai_provider
from app.services.ai.quiz_generation_service import QuizGenerationService

logger = logging.getLogger("mveousquiz.tasks")


@celery_app.task(name="quizzes.generate", bind=True, max_retries=2, default_retry_delay=5)
def generate_quiz_task(self, quiz_id: str) -> None:
    asyncio.run(_generate_quiz(uuid.UUID(quiz_id)))


async def _generate_quiz(quiz_id: uuid.UUID) -> None:
    async with TaskSessionLocal() as session:
        quiz = await session.get(Quiz, quiz_id)
        if quiz is None:
            logger.warning("Quiz %s not found for generation task", quiz_id)
            return

        try:
            provider = get_ai_provider()
            await QuizGenerationService(session, provider).generate_and_persist(quiz)
            quiz.status = QuizStatus.READY
        except Exception as exc:  # noqa: BLE001 - task boundary: persist failure, keep worker alive
            logger.exception("Quiz generation failed for %s", quiz_id)
            quiz.status = QuizStatus.FAILED
            quiz.error_message = str(exc)[:1000]

        await session.commit()
