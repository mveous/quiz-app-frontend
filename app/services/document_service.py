import uuid

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationFailedError
from app.models.document import Document
from app.models.enums import DocumentSourceType, DocumentStatus
from app.models.user import User
from app.repositories.document_repository import DocumentRepository
from app.utils.file_extraction import extract_text_from_pdf, extract_text_from_txt

_CONTENT_TYPE_SOURCE_TYPES = {
    "application/pdf": DocumentSourceType.PDF_UPLOAD,
    "text/plain": DocumentSourceType.TXT_UPLOAD,
}


class DocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._documents = DocumentRepository(session)

    async def create_from_upload(self, user: User, file: UploadFile, title: str) -> Document:
        source_type = self._resolve_source_type(file)
        data = await file.read()

        max_bytes = settings.document_max_file_size_mb * 1024 * 1024
        if len(data) > max_bytes:
            raise ValidationFailedError(
                f"File exceeds the {settings.document_max_file_size_mb}MB upload limit"
            )

        text = (
            extract_text_from_pdf(data)
            if source_type == DocumentSourceType.PDF_UPLOAD
            else extract_text_from_txt(data)
        )
        return await self._persist(user, title, source_type, text)

    async def create_from_paste(self, user: User, title: str, content: str) -> Document:
        return await self._persist(user, title, DocumentSourceType.PASTED_TEXT, content)

    async def list_for_user(self, user: User) -> list[Document]:
        return await self._documents.list_for_owner(user.id)

    async def get_owned(self, user: User, document_id: uuid.UUID) -> Document:
        document = await self._documents.get_by_id(document_id)
        if document is None:
            raise NotFoundError("Document not found")
        if document.owner_user_id != user.id:
            raise ForbiddenError("You do not have access to this document")
        return document

    async def delete_owned(self, user: User, document_id: uuid.UUID) -> None:
        document = await self.get_owned(user, document_id)
        await self._documents.delete(document)
        await self._session.commit()

    async def _persist(
        self, user: User, title: str, source_type: DocumentSourceType, text: str
    ) -> Document:
        text = text[: settings.document_max_chars]
        document = Document(
            owner_user_id=user.id,
            title=title,
            source_type=source_type,
            status=DocumentStatus.PROCESSING,
            raw_text=text,
            char_count=len(text),
        )
        await self._documents.create(document)
        await self._session.commit()

        celery_app.send_task("documents.ingest", args=[str(document.id)])
        return document

    @staticmethod
    def _resolve_source_type(file: UploadFile) -> DocumentSourceType:
        source_type = _CONTENT_TYPE_SOURCE_TYPES.get(file.content_type or "")
        if source_type is not None:
            return source_type

        # Browsers/clients don't always set a reliable content-type for these,
        # so fall back to the file extension.
        name = (file.filename or "").lower()
        if name.endswith(".pdf"):
            return DocumentSourceType.PDF_UPLOAD
        if name.endswith(".txt"):
            return DocumentSourceType.TXT_UPLOAD
        raise ValidationFailedError("Only .pdf and .txt files are supported")
