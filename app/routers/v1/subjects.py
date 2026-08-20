import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import APIResponse, success_response
from app.database.session import get_db
from app.middleware.auth import get_current_user
from app.models.taxonomy import Subject, Topic
from app.models.user import User
from app.schemas.quiz import SubjectOut, TopicOut

router = APIRouter(tags=["taxonomy"])


@router.get("/subjects", response_model=APIResponse[list[SubjectOut]])
async def list_subjects(
    session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    result = await session.execute(select(Subject).order_by(Subject.name))
    subjects = result.scalars().all()
    return success_response([SubjectOut.model_validate(s) for s in subjects])


@router.get("/subjects/{subject_id}/topics", response_model=APIResponse[list[TopicOut]])
async def list_topics(
    subject_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    result = await session.execute(
        select(Topic).where(Topic.subject_id == subject_id).order_by(Topic.name)
    )
    topics = result.scalars().all()
    return success_response([TopicOut.model_validate(t) for t in topics])
