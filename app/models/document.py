import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import DocumentSourceType, DocumentStatus


def _enum(python_enum, name: str):
    return Enum(python_enum, name=name, values_callable=lambda e: [m.value for m in e])


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user's personal knowledge-base upload (pasted text, .txt, or .pdf). Text is
    extracted at upload time and chunked/embedded asynchronously into `document_chunks`
    for RAG-grounded quiz generation. The original file is never stored — only the
    extracted text."""

    __tablename__ = "documents"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[DocumentSourceType] = mapped_column(
        _enum(DocumentSourceType, "document_source_type"), nullable=False
    )
    status: Mapped[DocumentStatus] = mapped_column(
        _enum(DocumentStatus, "document_status"), nullable=False, default=DocumentStatus.PROCESSING
    )
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class DocumentChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """RAG knowledge store. Populated asynchronously by the document-ingestion task.
    `owner_user_id` is denormalized from the parent `Document` (rather than requiring a
    join) so every retrieval query can filter on it directly — this is the guard against
    ever retrieving one user's private notes into another user's quiz generation."""

    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.ai_embedding_dim), nullable=False)
    doc_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
