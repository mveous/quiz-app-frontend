from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.services.ai.provider import AIProvider
from app.services.ai.text_chunker import chunk_text


class IngestionService:
    """Chunks and embeds a document's extracted text into `document_chunks`.
    Does not change `document.status` — the caller (the ingestion task) owns the
    document's lifecycle, matching how `QuizGenerationService` never sets
    `quiz.status` itself."""

    def __init__(self, session: AsyncSession, provider: AIProvider) -> None:
        self._session = session
        self._provider = provider

    async def ingest(self, document: Document) -> None:
        chunks = chunk_text(document.raw_text or "")
        if not chunks:
            raise ValueError("No content to chunk for this document")

        embeddings = await self._provider.embed(chunks)
        for index, (content, embedding) in enumerate(zip(chunks, embeddings)):
            self._session.add(
                DocumentChunk(
                    document_id=document.id,
                    owner_user_id=document.owner_user_id,
                    source_ref=document.title,
                    content=content,
                    embedding=embedding,
                    doc_metadata={"chunk_index": index},
                )
            )
        await self._session.flush()
