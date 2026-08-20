import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.responses import APIResponse, success_response
from app.database.session import get_db
from app.middleware.auth import get_current_user
from app.middleware.rate_limit import limiter
from app.models.user import User
from app.schemas.document import DocumentOut, DocumentPasteRequest
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload", response_model=APIResponse[DocumentOut], status_code=status.HTTP_201_CREATED
)
@limiter.limit(f"{settings.rate_limit_document_upload_per_minute}/minute")
async def upload_document(
    request: Request,
    title: str = Form(..., min_length=1, max_length=200),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    document = await DocumentService(session).create_from_upload(current_user, file, title)
    return success_response(DocumentOut.model_validate(document), "Document upload received")


@router.post(
    "/paste", response_model=APIResponse[DocumentOut], status_code=status.HTTP_201_CREATED
)
@limiter.limit(f"{settings.rate_limit_document_upload_per_minute}/minute")
async def paste_document(
    request: Request,
    data: DocumentPasteRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    document = await DocumentService(session).create_from_paste(
        current_user, data.title, data.content
    )
    return success_response(DocumentOut.model_validate(document), "Document received")


@router.get("", response_model=APIResponse[list[DocumentOut]])
async def list_documents(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    documents = await DocumentService(session).list_for_user(current_user)
    return success_response([DocumentOut.model_validate(d) for d in documents])


@router.get("/{document_id}", response_model=APIResponse[DocumentOut])
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    document = await DocumentService(session).get_owned(current_user, document_id)
    return success_response(DocumentOut.model_validate(document))


@router.delete("/{document_id}", response_model=APIResponse[None])
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await DocumentService(session).delete_owned(current_user, document_id)
    return success_response(None, "Document deleted")
