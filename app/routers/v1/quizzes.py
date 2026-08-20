import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.responses import APIResponse, success_response
from app.database.session import get_db
from app.middleware.auth import get_current_user
from app.middleware.rate_limit import limiter
from app.models.user import User
from app.schemas.quiz import QuestionOut, QuizGenerateRequest, QuizOut
from app.services.quiz_service import QuizService

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


@router.post(
    "/generate", response_model=APIResponse[QuizOut], status_code=status.HTTP_201_CREATED
)
@limiter.limit(f"{settings.rate_limit_ai_generation_per_minute}/minute")
async def generate_quiz(
    request: Request,
    data: QuizGenerateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    quiz = await QuizService(session).create_quiz(current_user, data)
    return success_response(QuizOut.model_validate(quiz), "Quiz generation started")


@router.post("/{quiz_id}/retry", response_model=APIResponse[QuizOut])
@limiter.limit(f"{settings.rate_limit_ai_generation_per_minute}/minute")
async def retry_quiz(
    request: Request,
    quiz_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    quiz = await QuizService(session).retry_quiz(current_user, quiz_id)
    return success_response(QuizOut.model_validate(quiz), "Quiz generation restarted")


@router.get("", response_model=APIResponse[list[QuizOut]])
async def list_quizzes(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    quizzes = await QuizService(session).list_quizzes_for_user(current_user)
    return success_response([QuizOut.model_validate(q) for q in quizzes])


@router.get("/{quiz_id}", response_model=APIResponse[QuizOut])
async def get_quiz(
    quiz_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    quiz, questions = await QuizService(session).get_quiz_with_questions(current_user, quiz_id)
    quiz_out = QuizOut.model_validate(quiz)
    quiz_out.questions = [QuestionOut.model_validate(q) for q in questions]
    return success_response(quiz_out)
