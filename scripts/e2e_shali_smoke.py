"""One-off manual smoke test: real (non-mock) Shali v1 quiz generation + document
embedding, driven over HTTP against a locally running uvicorn instance.

Not part of the pytest suite (pytest forces AI_PROVIDER=mock) - run manually:

    python scripts/e2e_shali_smoke.py
"""

import time

import httpx

BASE = "http://127.0.0.1:8000/api/v1"


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=30) as client:
        email = f"shali-smoke-{int(time.time())}@example.com"
        password = "Str0ngPassw0rd!"

        r = client.post(
            "/auth/register",
            json={"email": email, "password": password, "full_name": "Smoke Test", "country_code": "IN"},
        )
        print("register:", r.status_code)
        r.raise_for_status()

        r = client.post("/auth/login", json={"email": email, "password": password})
        r.raise_for_status()
        token = r.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r = client.post(
            "/documents/paste",
            headers=headers,
            json={
                "title": "Smoke notes",
                "content": "Photosynthesis converts light energy into chemical energy in plants." * 5,
            },
        )
        print("document paste:", r.status_code)
        r.raise_for_status()
        document_id = r.json()["data"]["id"]

        for _ in range(60):
            r = client.get(f"/documents/{document_id}", headers=headers)
            status = r.json()["data"]["status"]
            print("document status:", status)
            if status in ("ready", "failed"):
                break
            time.sleep(3)
        assert status == "ready", f"document ingestion did not reach ready: {status}"

        r = client.post(
            "/quizzes/generate",
            headers=headers,
            json={
                "topic_text": "Photosynthesis basics",
                "question_count": 2,
                "difficulty": "easy",
                "question_types": ["mcq"],
                "use_my_documents": True,
            },
        )
        print("quiz generate:", r.status_code, r.text[:300])
        r.raise_for_status()
        quiz_id = r.json()["data"]["id"]

        status = None
        for _ in range(60):
            r = client.get(f"/quizzes/{quiz_id}", headers=headers)
            status = r.json()["data"]["status"]
            print("quiz status:", status)
            if status in ("ready", "failed"):
                break
            time.sleep(3)
        assert status == "ready", f"quiz generation did not reach ready: {status}"

        r = client.get(f"/quizzes/{quiz_id}", headers=headers)
        questions = r.json()["data"]["questions"]
        print(f"generated {len(questions)} real (non-mock) questions:")
        for q in questions:
            print(" -", q["type"], "|", q["prompt"][:100])

        print("\nSMOKE TEST PASSED")


if __name__ == "__main__":
    main()
