import uuid

import pytest

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
    quiz_id = response.json()["data"]["id"]
    await _generate_quiz(uuid.UUID(quiz_id))
    ready = await client.get(f"/api/v1/quizzes/{quiz_id}", headers=headers)
    return ready.json()["data"]


async def _complete_attempt(client, headers, quiz) -> str:
    start = await client.post(f"/api/v1/quizzes/{quiz['id']}/attempts", headers=headers)
    attempt_id = start.json()["data"]["id"]

    for question in quiz["questions"]:
        if question["type"] == "mcq":
            correct_option = next(o for o in question["options"] if o["text"] == "Correct option B")
            await client.post(
                f"/api/v1/attempts/{attempt_id}/answers",
                json={"question_id": question["id"], "selected_option_id": correct_option["id"]},
                headers=headers,
            )
        elif question["type"] == "short_answer":
            await client.post(
                f"/api/v1/attempts/{attempt_id}/answers",
                json={"question_id": question["id"], "response_text": "mock reference answer"},
                headers=headers,
            )

    await client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=headers)
    return attempt_id


async def test_report_includes_bloom_level_and_breakdown(client, registered_user):
    headers, _ = await registered_user()
    quiz = await _generate_ready_quiz(client, headers)
    attempt_id = await _complete_attempt(client, headers, quiz)

    report = (await client.get(f"/api/v1/attempts/{attempt_id}/report", headers=headers)).json()["data"]

    assert all(q["bloom_level"] is not None for q in report["questions"])
    assert any(v is not None for v in report["bloom_breakdown"].values())


async def test_trend_previous_accuracy_matches_prior_attempt(client, registered_user):
    headers, _ = await registered_user()

    quiz1 = await _generate_ready_quiz(client, headers, topic_text="First quiz")
    attempt1_id = await _complete_attempt(client, headers, quiz1)
    report1 = (await client.get(f"/api/v1/attempts/{attempt1_id}/report", headers=headers)).json()["data"]

    quiz2 = await _generate_ready_quiz(client, headers, topic_text="Second quiz")
    attempt2_id = await _complete_attempt(client, headers, quiz2)
    report2 = (await client.get(f"/api/v1/attempts/{attempt2_id}/report", headers=headers)).json()["data"]

    assert report2["trend"]["previous_attempt_accuracy"] == report1["accuracy"]


async def test_trend_average_recent_accuracy_over_three_attempts(client, registered_user):
    headers, _ = await registered_user()
    accuracies = []
    report = None
    for i in range(3):
        quiz = await _generate_ready_quiz(client, headers, topic_text=f"Quiz {i}")
        attempt_id = await _complete_attempt(client, headers, quiz)
        report = (await client.get(f"/api/v1/attempts/{attempt_id}/report", headers=headers)).json()["data"]
        accuracies.append(report["accuracy"])

    expected_average = round(sum(accuracies[:2]) / 2, 2)
    assert report["trend"]["average_recent_accuracy"] == expected_average


async def test_attempt_history_returns_only_own_submitted_attempts(client, registered_user):
    headers, _ = await registered_user("history-owner@example.com")
    quiz = await _generate_ready_quiz(client, headers)
    await _complete_attempt(client, headers, quiz)

    other_headers, _ = await registered_user("history-other@example.com")
    other_quiz = await _generate_ready_quiz(client, other_headers)
    await _complete_attempt(client, other_headers, other_quiz)

    response = await client.get("/api/v1/attempts/history", headers=headers)
    assert response.status_code == 200
    history = response.json()["data"]
    assert len(history) == 1
    assert history[0]["quiz_id"] == quiz["id"]


async def test_report_not_available_before_submission(client, registered_user):
    headers, _ = await registered_user()
    quiz = await _generate_ready_quiz(client, headers)
    start = await client.post(f"/api/v1/quizzes/{quiz['id']}/attempts", headers=headers)
    attempt_id = start.json()["data"]["id"]

    response = await client.get(f"/api/v1/attempts/{attempt_id}/report", headers=headers)
    assert response.status_code == 422
