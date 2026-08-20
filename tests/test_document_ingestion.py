import io
import uuid

import pytest
from reportlab.pdfgen import canvas

from app.tasks.document_tasks import _ingest_document

pytestmark = pytest.mark.asyncio


def _make_pdf_bytes(text: str) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, text)
    c.save()
    return buffer.getvalue()


async def _upload_and_ingest(client, headers, *, filename, content, content_type, title="My notes"):
    response = await client.post(
        "/api/v1/documents/upload",
        data={"title": title},
        files={"file": (filename, content, content_type)},
        headers=headers,
    )
    assert response.status_code == 201
    document_id = response.json()["data"]["id"]
    await _ingest_document(uuid.UUID(document_id))
    get_response = await client.get(f"/api/v1/documents/{document_id}", headers=headers)
    return get_response.json()["data"]


async def test_upload_txt_document_becomes_ready(client, registered_user):
    headers, _ = await registered_user()
    document = await _upload_and_ingest(
        client,
        headers,
        filename="notes.txt",
        content=b"Mitochondria is the powerhouse of the cell.\n\nIt produces ATP through respiration.",
        content_type="text/plain",
    )
    assert document["status"] == "ready"
    assert document["source_type"] == "txt_upload"
    assert document["char_count"] > 0


async def test_upload_pdf_document_becomes_ready(client, registered_user):
    headers, _ = await registered_user()
    pdf_bytes = _make_pdf_bytes("Newton's laws describe the relationship between forces and motion.")
    document = await _upload_and_ingest(
        client, headers, filename="notes.pdf", content=pdf_bytes, content_type="application/pdf"
    )
    assert document["status"] == "ready"
    assert document["source_type"] == "pdf_upload"


async def test_paste_document_becomes_ready(client, registered_user):
    headers, _ = await registered_user()
    response = await client.post(
        "/api/v1/documents/paste",
        json={"title": "Pasted notes", "content": "The mitochondria is the powerhouse of the cell."},
        headers=headers,
    )
    assert response.status_code == 201
    document_id = response.json()["data"]["id"]
    await _ingest_document(uuid.UUID(document_id))

    get_response = await client.get(f"/api/v1/documents/{document_id}", headers=headers)
    document = get_response.json()["data"]
    assert document["status"] == "ready"
    assert document["source_type"] == "pasted_text"


async def test_list_documents_returns_only_own(client, registered_user):
    headers, _ = await registered_user("doc-owner@example.com")
    await client.post(
        "/api/v1/documents/paste",
        json={"title": "Owner notes", "content": "Owner content here."},
        headers=headers,
    )
    other_headers, _ = await registered_user("doc-other@example.com")
    await client.post(
        "/api/v1/documents/paste",
        json={"title": "Other notes", "content": "Other content here."},
        headers=other_headers,
    )

    response = await client.get("/api/v1/documents", headers=headers)
    titles = [d["title"] for d in response.json()["data"]]
    assert titles == ["Owner notes"]


async def test_upload_document_requires_authentication(client):
    response = await client.post(
        "/api/v1/documents/upload",
        data={"title": "x"},
        files={"file": ("a.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 401


async def test_unsupported_file_type_rejected(client, registered_user):
    headers, _ = await registered_user()
    response = await client.post(
        "/api/v1/documents/upload",
        data={"title": "Bad file"},
        files={"file": ("notes.docx", b"whatever", "application/msword")},
        headers=headers,
    )
    assert response.status_code == 422


async def test_empty_txt_file_rejected(client, registered_user):
    headers, _ = await registered_user()
    response = await client.post(
        "/api/v1/documents/upload",
        data={"title": "Empty"},
        files={"file": ("empty.txt", b"   ", "text/plain")},
        headers=headers,
    )
    assert response.status_code == 422


async def test_oversized_file_rejected(client, registered_user):
    headers, _ = await registered_user()
    oversized = b"a" * (6 * 1024 * 1024)  # default limit is 5MB
    response = await client.post(
        "/api/v1/documents/upload",
        data={"title": "Too big"},
        files={"file": ("big.txt", oversized, "text/plain")},
        headers=headers,
    )
    assert response.status_code == 422


async def test_other_user_cannot_get_or_delete_document(client, registered_user):
    headers, _ = await registered_user("doc-owner2@example.com")
    response = await client.post(
        "/api/v1/documents/paste",
        json={"title": "Private notes", "content": "Secret content."},
        headers=headers,
    )
    document_id = response.json()["data"]["id"]

    other_headers, _ = await registered_user("doc-intruder@example.com")
    get_response = await client.get(f"/api/v1/documents/{document_id}", headers=other_headers)
    assert get_response.status_code == 403

    delete_response = await client.delete(f"/api/v1/documents/{document_id}", headers=other_headers)
    assert delete_response.status_code == 403


async def test_owner_can_delete_document(client, registered_user):
    headers, _ = await registered_user()
    response = await client.post(
        "/api/v1/documents/paste",
        json={"title": "To delete", "content": "Some content to delete."},
        headers=headers,
    )
    document_id = response.json()["data"]["id"]

    delete_response = await client.delete(f"/api/v1/documents/{document_id}", headers=headers)
    assert delete_response.status_code == 200

    get_response = await client.get(f"/api/v1/documents/{document_id}", headers=headers)
    assert get_response.status_code == 404
