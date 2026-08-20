import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import APIResponse, success_response
from app.database.session import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.attempt import (
    AnswerOut,
    AnswerSubmitRequest,
    AttemptOut,
    AttemptReportOut,
    AttemptSummaryOut,
)
from app.services.attempt_service import AttemptService
from app.services.report_service import ReportService

router = APIRouter(tags=["attempts"])


@router.post(
    "/quizzes/{quiz_id}/attempts",
    response_model=APIResponse[AttemptOut],
    status_code=status.HTTP_201_CREATED,
)
async def start_attempt(
    quiz_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    attempt = await AttemptService(session).start_attempt(current_user, quiz_id)
    return success_response(AttemptOut.model_validate(attempt), "Attempt started")


@router.post("/attempts/{attempt_id}/answers", response_model=APIResponse[AnswerOut])
async def submit_answer(
    attempt_id: uuid.UUID,
    data: AnswerSubmitRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    answer = await AttemptService(session).submit_answer(current_user, attempt_id, data)
    return success_response(AnswerOut.model_validate(answer), "Answer saved")


@router.post("/attempts/{attempt_id}/submit", response_model=APIResponse[AttemptOut])
async def submit_attempt(
    attempt_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    attempt = await AttemptService(session).submit_attempt(current_user, attempt_id)
    return success_response(AttemptOut.model_validate(attempt), "Attempt submitted")


@router.get("/attempts/{attempt_id}/report", response_model=APIResponse[AttemptReportOut])
async def get_report(
    attempt_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    report = await ReportService(session).get_report(current_user, attempt_id)
    return success_response(report, "Report generated")


@router.get("/attempts/history", response_model=APIResponse[list[AttemptSummaryOut]])
async def get_attempt_history(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    history = await ReportService(session).list_history(current_user)
    return success_response(history)


@router.get("/attempts/{attempt_id}/report/export")
async def export_report(
    attempt_id: uuid.UUID,
    format: Literal["pdf", "csv"],
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    content, media_type, filename = await ReportService(session).export(
        current_user, attempt_id, format
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
