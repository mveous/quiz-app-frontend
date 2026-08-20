import uuid

import pytest

from app.database.session import AsyncSessionLocal
from app.services.ai import quiz_generation_service as qgs_module
from app.services.ai.providers.mock_provider import MockAIProvider
from app.services.ai.retrieval_service import RetrievalService
from app.tasks.document_tasks import _ingest_document
from app.tasks.quiz_tasks import _generate_quiz

pytestmark = pytest.mark.asyncio


async def _get_user_id(client, headers) -> uuid.UUID:
    response = await client.get("/api/v1/auth/me", headers=headers)
    return uuid.UUID(response.json()["data"]["id"])


async def _create_ready_document(client, headers, title: str, content: str) -> str:
    response = await client.post(
        "/api/v1/documents/paste", json={"title": title, "content": content}, headers=headers
    )
    document_id = response.json()["data"]["id"]
    await _ingest_document(uuid.UUID(document_id))
    return document_id


async def test_retrieval_returns_empty_for_user_with_no_documents(client, registered_user):
    headers, _ = await registered_user()
    user_id = await _get_user_id(client, headers)

    async with AsyncSessionLocal() as session:
        context = await RetrievalService(session, MockAIProvider()).build_context(
            user_id, "Photosynthesis"
        )
    assert context == []


async def test_retrieval_returns_only_the_requesting_users_chunks(client, registered_user):
    headers_a, _ = await registered_user("rag-user-a@example.com")
    user_a_id = await _get_user_id(client, headers_a)
    await _create_ready_document(
        client, headers_a, "User A notes", "Photosynthesis converts sunlight into chemical energy."
    )

    headers_b, _ = await registered_user("rag-user-b@example.com")
    await _create_ready_document(
        client,
        headers_b,
        "User B notes",
        "UNIQUE_MARKER_ONLY_USER_B_SHOULD_SEE this is user B's private content.",
    )

    async with AsyncSessionLocal() as session:
        context = await RetrievalService(session, MockAIProvider()).build_context(
            user_a_id, "Photosynthesis"
        )

    assert context, "expected at least one chunk retrieved for user A"
    assert all("UNIQUE_MARKER_ONLY_USER_B_SHOULD_SEE" not in chunk for chunk in context)


async def test_quiz_generation_with_zero_documents_still_succeeds(client, registered_user):
    """Regression guard: a document-free quiz must generate exactly as it did
    before RAG grounding existed (prompt-only degradation)."""
    headers, _ = await registered_user()
    response = await client.post(
        "/api/v1/quizzes/generate",
        json={"topic_text": "Algebra", "question_count": 3, "use_my_documents": True},
        headers=headers,
    )
    assert response.status_code == 201
    quiz_id = response.json()["data"]["id"]
    await _generate_quiz(uuid.UUID(quiz_id))

    quiz = (await client.get(f"/api/v1/quizzes/{quiz_id}", headers=headers)).json()["data"]
    assert quiz["status"] == "ready"
    assert len(quiz["questions"]) == 3


async def test_quiz_generation_with_ready_documents_still_succeeds(client, registered_user):
    headers, _ = await registered_user()
    await _create_ready_document(client, headers, "Notes", "Some study notes about biology.")

    response = await client.post(
        "/api/v1/quizzes/generate",
        json={"topic_text": "Biology", "question_count": 3, "use_my_documents": True},
        headers=headers,
    )
    quiz_id = response.json()["data"]["id"]
    await _generate_quiz(uuid.UUID(quiz_id))

    quiz = (await client.get(f"/api/v1/quizzes/{quiz_id}", headers=headers)).json()["data"]
    assert quiz["status"] == "ready"


async def test_use_my_documents_true_triggers_retrieval(client, registered_user, monkeypatch):
    calls: list[uuid.UUID] = []
    original = qgs_module.RetrievalService.build_context

    async def spy(self, owner_user_id, query_text, top_k=None):
        calls.append(owner_user_id)
        return await original(self, owner_user_id, query_text, top_k)

    monkeypatch.setattr(qgs_module.RetrievalService, "build_context", spy)

    headers, _ = await registered_user()
    response = await client.post(
        "/api/v1/quizzes/generate",
        json={"topic_text": "Chemistry", "question_count": 3, "use_my_documents": True},
        headers=headers,
    )
    quiz_id = response.json()["data"]["id"]
    await _generate_quiz(uuid.UUID(quiz_id))

    assert len(calls) == 1


async def test_use_my_documents_false_skips_retrieval(client, registered_user, monkeypatch):
    calls: list[uuid.UUID] = []

    async def spy(self, owner_user_id, query_text, top_k=None):
        calls.append(owner_user_id)
        return []

    monkeypatch.setattr(qgs_module.RetrievalService, "build_context", spy)

    headers, _ = await registered_user()
    await _create_ready_document(client, headers, "Notes", "Some study notes.")

    response = await client.post(
        "/api/v1/quizzes/generate",
        json={"topic_text": "Chemistry", "question_count": 3, "use_my_documents": False},
        headers=headers,
    )
    quiz_id = response.json()["data"]["id"]
    await _generate_quiz(uuid.UUID(quiz_id))

    assert len(calls) == 0
