import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.document_repository import DocumentChunkRepository
from app.services.ai.provider import AIProvider


class RetrievalService:
    """Builds RAG context from a user's own ready document chunks. Returns an empty
    list whenever there's nothing to retrieve (no query text, no chunks yet) so quiz
    generation always degrades gracefully to prompt-only rather than failing."""

    def __init__(self, session: AsyncSession, provider: AIProvider) -> None:
        self._provider = provider
        self._chunks = DocumentChunkRepository(session)

    async def build_context(
        self, owner_user_id: uuid.UUID, query_text: str, top_k: int | None = None
    ) -> list[str]:
        if not query_text.strip():
            return []

        query_embedding = (await self._provider.embed([query_text]))[0]
        chunks = await self._chunks.search_similar(
            owner_user_id, query_embedding, top_k or settings.rag_top_k
        )

        context: list[str] = []
        total_chars = 0
        for chunk in chunks:
            if total_chars + len(chunk.content) > settings.rag_max_context_chars:
                break
            context.append(chunk.content)
            total_chars += len(chunk.content)
        return context
