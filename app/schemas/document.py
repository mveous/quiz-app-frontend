import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DocumentSourceType, DocumentStatus


class DocumentPasteRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=200_000)


class DocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    source_type: DocumentSourceType
    status: DocumentStatus
    char_count: int | None
    error_message: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
