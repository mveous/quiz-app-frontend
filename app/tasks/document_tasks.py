import asyncio
import logging
import uuid

from app.core.celery_app import celery_app
from app.database.session import TaskSessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.ai.factory import get_ai_provider
from app.services.ai.ingestion_service import IngestionService

logger = logging.getLogger("mveousquiz.tasks")


@celery_app.task(name="documents.ingest", bind=True, max_retries=2, default_retry_delay=5)
def ingest_document_task(self, document_id: str) -> None:
    asyncio.run(_ingest_document(uuid.UUID(document_id)))


async def _ingest_document(document_id: uuid.UUID) -> None:
    # Uses TaskSessionLocal (NullPool), not the FastAPI pooled engine: a pooled
    # connection checked out under one Celery task's event loop is invalid once that
    # loop closes (see .ai/issues.md #1, hit by the identical quiz-generation task).
    async with TaskSessionLocal() as session:
        document = await session.get(Document, document_id)
        if document is None:
            logger.warning("Document %s not found for ingestion task", document_id)
            return

        try:
            provider = get_ai_provider()
            await IngestionService(session, provider).ingest(document)
            document.status = DocumentStatus.READY
        except Exception as exc:  # noqa: BLE001 - task boundary: persist failure, keep worker alive
            logger.exception("Document ingestion failed for %s", document_id)
            document.status = DocumentStatus.FAILED
            document.error_message = str(exc)[:1000]

        await session.commit()
