import uuid

import pytest

from app.tasks.quiz_tasks import _generate_quiz

pytestmark = pytest.mark.asyncio


async def _generate_ready_quiz(client, headers, **overrides):
    payload = {
        "topic_text": "Photosynthesis",
        "question_count": 3,
        "difficulty": "medium",
        "question_types": ["mcq"],
        **overrides,
    }
    response = await client.post("/api/v1/quizzes/generate", json=payload, headers=headers)
    quiz_id = response.json()["data"]["id"]
    await _generate_quiz(uuid.UUID(quiz_id))
    ready = await client.get(f"/api/v1/quizzes/{quiz_id}", headers=headers)
    return ready.json()["data"]


async def _submit_attempt(client, headers, quiz) -> str:
    start = await client.post(f"/api/v1/quizzes/{quiz['id']}/attempts", headers=headers)
    attempt_id = start.json()["data"]["id"]
    for question in quiz["questions"]:
        correct_option = next(o for o in question["options"] if o["text"] == "Correct option B")
        await client.post(
            f"/api/v1/attempts/{attempt_id}/answers",
            json={"question_id": question["id"], "selected_option_id": correct_option["id"]},
            headers=headers,
        )
    await client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=headers)
    return attempt_id


async def test_export_csv(client, registered_user):
    headers, _ = await registered_user()
    quiz = await _generate_ready_quiz(client, headers)
    attempt_id = await _submit_attempt(client, headers, quiz)

    response = await client.get(
        f"/api/v1/attempts/{attempt_id}/report/export", params={"format": "csv"}, headers=headers
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = response.text.strip().splitlines()
    assert len(rows) == len(quiz["questions"]) + 1  # header + one row per question


async def test_export_pdf(client, registered_user):
    headers, _ = await registered_user()
    quiz = await _generate_ready_quiz(client, headers)
    attempt_id = await _submit_attempt(client, headers, quiz)

    response = await client.get(
        f"/api/v1/attempts/{attempt_id}/report/export", params={"format": "pdf"}, headers=headers
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 100


async def test_export_invalid_format_rejected(client, registered_user):
    headers, _ = await registered_user()
    quiz = await _generate_ready_quiz(client, headers)
    attempt_id = await _submit_attempt(client, headers, quiz)

    response = await client.get(
        f"/api/v1/attempts/{attempt_id}/report/export", params={"format": "xlsx"}, headers=headers
    )
    assert response.status_code == 422


async def test_export_before_submission_rejected(client, registered_user):
    headers, _ = await registered_user()
    quiz = await _generate_ready_quiz(client, headers)
    start = await client.post(f"/api/v1/quizzes/{quiz['id']}/attempts", headers=headers)
    attempt_id = start.json()["data"]["id"]

    response = await client.get(
        f"/api/v1/attempts/{attempt_id}/report/export", params={"format": "csv"}, headers=headers
    )
    assert response.status_code == 422


async def test_other_user_cannot_export_report(client, registered_user):
    headers, _ = await registered_user("export-owner@example.com")
    quiz = await _generate_ready_quiz(client, headers)
    attempt_id = await _submit_attempt(client, headers, quiz)

    other_headers, _ = await registered_user("export-intruder@example.com")
    response = await client.get(
        f"/api/v1/attempts/{attempt_id}/report/export", params={"format": "csv"}, headers=other_headers
    )
    assert response.status_code == 403
