import uuid

import httpx
import pytest

from app.core.config import settings
from app.services.ai import quiz_generation_service as qgs_module
from app.services.ai.web_search_service import WebSearchService
from app.tasks.quiz_tasks import _generate_quiz

pytestmark = pytest.mark.asyncio


async def test_search_topic_returns_empty_for_blank_query():
    context = await WebSearchService().search_topic("   ")
    assert context == []


async def test_search_topic_returns_empty_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "web_search_enabled", False)
    context = await WebSearchService().search_topic("Photosynthesis")
    assert context == []


async def test_search_topic_degrades_gracefully_on_network_failure(monkeypatch):
    monkeypatch.setattr(settings, "web_search_enabled", True)

    async def broken_get(*args, **kwargs):
        raise httpx.ConnectError("no network in this test")

    monkeypatch.setattr(httpx.AsyncClient, "get", broken_get)

    context = await WebSearchService().search_topic("Photosynthesis")
    assert context == []


async def test_use_web_search_true_triggers_search(client, registered_user, monkeypatch):
    calls: list[str] = []

    async def spy(self, query, max_articles=None):
        calls.append(query)
        return ["From Wikipedia — Chemistry:\nChemistry is the study of matter."]

    monkeypatch.setattr(qgs_module.WebSearchService, "search_topic", spy)

    headers, _ = await registered_user()
    response = await client.post(
        "/api/v1/quizzes/generate",
        json={"topic_text": "Chemistry", "question_count": 3, "use_web_search": True},
        headers=headers,
    )
    quiz_id = response.json()["data"]["id"]
    await _generate_quiz(uuid.UUID(quiz_id))

    assert len(calls) == 1
    quiz = (await client.get(f"/api/v1/quizzes/{quiz_id}", headers=headers)).json()["data"]
    assert quiz["status"] == "ready"


async def test_use_web_search_false_skips_search(client, registered_user, monkeypatch):
    calls: list[str] = []

    async def spy(self, query, max_articles=None):
        calls.append(query)
        return []

    monkeypatch.setattr(qgs_module.WebSearchService, "search_topic", spy)

    headers, _ = await registered_user()
    response = await client.post(
        "/api/v1/quizzes/generate",
        json={"topic_text": "Chemistry", "question_count": 3, "use_web_search": False},
        headers=headers,
    )
    quiz_id = response.json()["data"]["id"]
    await _generate_quiz(uuid.UUID(quiz_id))

    assert len(calls) == 0
