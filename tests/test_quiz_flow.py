import uuid

import pytest
from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.enums import QuizStatus
from app.models.quiz import Question, Quiz
from app.tasks.quiz_tasks import _generate_quiz

pytestmark = pytest.mark.asyncio


async def _generate_ready_quiz(client, headers, **overrides):
    payload = {
        "topic_text": "Photosynthesis",
        "question_count": 4,
        "difficulty": "medium",
        "question_types": ["mcq", "short_answer"],
        **overrides,
    }
    response = await client.post("/api/v1/quizzes/generate", json=payload, headers=headers)
    assert response.status_code == 201
    quiz_id = response.json()["data"]["id"]

    # No Celery worker runs in tests; execute the generation task body directly
    # against the same test database so the quiz transitions to "ready".
    await _generate_quiz(uuid.UUID(quiz_id))

    ready_response = await client.get(f"/api/v1/quizzes/{quiz_id}", headers=headers)
    return ready_response.json()["data"]


async def test_generate_quiz_requires_authentication(client):
    response = await client.post(
        "/api/v1/quizzes/generate", json={"topic_text": "Algebra", "question_count": 3}
    )
    assert response.status_code == 401


async def test_generate_quiz_requires_a_source(client, registered_user):
    headers, _ = await registered_user()
    response = await client.post(
        "/api/v1/quizzes/generate", json={"question_count": 3}, headers=headers
    )
    assert response.status_code == 422


async def test_generate_quiz_produces_requested_question_mix(client, registered_user):
    headers, _ = await registered_user()
    quiz = await _generate_ready_quiz(client, headers, question_count=4)

    assert quiz["status"] == "ready"
    assert len(quiz["questions"]) == 4
    types = [q["type"] for q in quiz["questions"]]
    assert types.count("mcq") == 2
    assert types.count("short_answer") == 2
    # Correctness must never be exposed on the take-quiz view.
    for question in quiz["questions"]:
        for option in question["options"]:
            assert "is_correct" not in option

    # Regression guard: a document-free (Module 1 style) quiz must still generate
    # unchanged after Module 2's RAG grounding + Bloom classification were added —
    # every question still gets persisted with a classified bloom_level.
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Question).where(Question.quiz_id == uuid.UUID(quiz["id"])))
        persisted_questions = result.scalars().all()
    assert len(persisted_questions) == 4
    assert all(q.bloom_level is not None for q in persisted_questions)


async def test_list_quizzes_returns_only_own_quizzes_newest_first(client, registered_user):
    headers, _ = await registered_user("history@example.com")
    first = await _generate_ready_quiz(client, headers, topic_text="First quiz")
    second = await _generate_ready_quiz(client, headers, topic_text="Second quiz")

    other_headers, _ = await registered_user("other-history@example.com")
    await _generate_ready_quiz(client, other_headers, topic_text="Someone else's quiz")

    response = await client.get("/api/v1/quizzes", headers=headers)
    assert response.status_code == 200
    quiz_ids = [q["id"] for q in response.json()["data"]]
    assert quiz_ids == [second["id"], first["id"]]


async def test_quiz_is_not_visible_to_other_users(client, registered_user):
    headers, _ = await registered_user("owner@example.com")
    quiz = await _generate_ready_quiz(client, headers)

    other_headers, _ = await registered_user("intruder@example.com")
    response = await client.get(f"/api/v1/quizzes/{quiz['id']}", headers=other_headers)
    assert response.status_code == 403


async def test_full_attempt_and_report_flow(client, registered_user):
    headers, _ = await registered_user()
    quiz = await _generate_ready_quiz(client, headers)
    questions = quiz["questions"]

    start_response = await client.post(
        f"/api/v1/quizzes/{quiz['id']}/attempts", headers=headers
    )
    assert start_response.status_code == 201
    attempt_id = start_response.json()["data"]["id"]

    mcq_question = next(q for q in questions if q["type"] == "mcq")
    correct_option = next(o for o in mcq_question["options"] if o["text"] == "Correct option B")
    answer_response = await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"question_id": mcq_question["id"], "selected_option_id": correct_option["id"]},
        headers=headers,
    )
    assert answer_response.status_code == 200

    short_answer_question = next(q for q in questions if q["type"] == "short_answer")
    await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"question_id": short_answer_question["id"], "response_text": "mock reference answer"},
        headers=headers,
    )
    # Remaining questions are left unanswered on purpose to exercise that path.

    submit_response = await client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=headers)
    assert submit_response.status_code == 200
    submitted = submit_response.json()["data"]
    assert submitted["status"] == "submitted"
    assert submitted["score"] >= 2.0

    report_response = await client.get(f"/api/v1/attempts/{attempt_id}/report", headers=headers)
    report = report_response.json()["data"]
    assert report_response.status_code == 200
    assert len(report["questions"]) == len(questions)
    assert any(q["is_correct"] for q in report["questions"])
    assert all(q["ai_feedback"] for q in report["questions"])


async def test_retry_regenerates_a_failed_quiz(client, registered_user):
    headers, _ = await registered_user()
    response = await client.post(
        "/api/v1/quizzes/generate",
        json={"topic_text": "Algebra", "question_count": 3},
        headers=headers,
    )
    quiz_id = response.json()["data"]["id"]

    async with AsyncSessionLocal() as session:
        quiz = await session.get(Quiz, uuid.UUID(quiz_id))
        quiz.status = QuizStatus.FAILED
        quiz.error_message = "AI provider returned an invalid quiz payload"
        await session.commit()

    retry_response = await client.post(f"/api/v1/quizzes/{quiz_id}/retry", headers=headers)
    assert retry_response.status_code == 200
    retried = retry_response.json()["data"]
    assert retried["status"] == "generating"
    assert retried["error_message"] is None

    await _generate_quiz(uuid.UUID(quiz_id))

    ready_response = await client.get(f"/api/v1/quizzes/{quiz_id}", headers=headers)
    ready = ready_response.json()["data"]
    assert ready["status"] == "ready"
    assert len(ready["questions"]) == 3


async def test_cannot_retry_a_quiz_that_is_not_failed(client, registered_user):
    headers, _ = await registered_user()
    quiz = await _generate_ready_quiz(client, headers)

    retry_response = await client.post(f"/api/v1/quizzes/{quiz['id']}/retry", headers=headers)
    assert retry_response.status_code == 422


async def test_cannot_start_attempt_while_quiz_is_generating(client, registered_user):
    headers, _ = await registered_user()
    response = await client.post(
        "/api/v1/quizzes/generate",
        json={"topic_text": "Algebra", "question_count": 3},
        headers=headers,
    )
    quiz_id = response.json()["data"]["id"]

    start_response = await client.post(f"/api/v1/quizzes/{quiz_id}/attempts", headers=headers)
    assert start_response.status_code == 422


async def test_cannot_answer_after_attempt_submitted(client, registered_user):
    headers, _ = await registered_user()
    quiz = await _generate_ready_quiz(client, headers)
    start_response = await client.post(
        f"/api/v1/quizzes/{quiz['id']}/attempts", headers=headers
    )
    attempt_id = start_response.json()["data"]["id"]

    await client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=headers)

    late_answer = await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"question_id": quiz["questions"][0]["id"], "response_text": "too late"},
        headers=headers,
    )
    assert late_answer.status_code == 422


async def test_starting_attempt_twice_resumes_same_attempt(client, registered_user):
    """Regression guard: re-entering a quiz that's already in progress (e.g. a
    browser back-navigation remount) must resume the existing attempt and its
    saved answers, not silently spawn a second blank attempt."""
    headers, _ = await registered_user()
    quiz = await _generate_ready_quiz(client, headers)
    question = quiz["questions"][0]

    first = await client.post(f"/api/v1/quizzes/{quiz['id']}/attempts", headers=headers)
    attempt_id = first.json()["data"]["id"]

    await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"question_id": question["id"], "response_text": "in-progress answer"},
        headers=headers,
    )

    second = await client.post(f"/api/v1/quizzes/{quiz['id']}/attempts", headers=headers)
    assert second.status_code == 201
    resumed = second.json()["data"]
    assert resumed["id"] == attempt_id
    assert len(resumed["answers"]) == 1
    assert resumed["answers"][0]["question_id"] == question["id"]


async def test_other_user_cannot_access_attempt(client, registered_user):
    headers, _ = await registered_user("owner2@example.com")
    quiz = await _generate_ready_quiz(client, headers)
    start_response = await client.post(
        f"/api/v1/quizzes/{quiz['id']}/attempts", headers=headers
    )
    attempt_id = start_response.json()["data"]["id"]

    other_headers, _ = await registered_user("intruder2@example.com")
    response = await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"question_id": quiz["questions"][0]["id"], "response_text": "hijack attempt"},
        headers=other_headers,
    )
    assert response.status_code == 403
