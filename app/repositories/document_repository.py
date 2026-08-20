import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, document: Document) -> Document:
        self._session.add(document)
        await self._session.flush()
        return document

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        result = await self._session.execute(select(Document).where(Document.id == document_id))
        return result.scalar_one_or_none()

    async def list_for_owner(self, owner_user_id: uuid.UUID, limit: int = 50) -> list[Document]:
        result = await self._session.execute(
            select(Document)
            .where(Document.owner_user_id == owner_user_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete(self, document: Document) -> None:
        await self._session.delete(document)
        await self._session.flush()


class DocumentChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search_similar(
        self, owner_user_id: uuid.UUID, query_embedding: list[float], top_k: int
    ) -> list[DocumentChunk]:
        # owner_user_id is a required positional argument, not an optional kwarg —
        # deliberately structured so this can never be called without a tenant
        # filter. A bug here would leak one user's private notes into another
        # user's AI-generated quiz content.
        result = await self._session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.owner_user_id == owner_user_id)
            .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )
        return list(result.scalars().all())
