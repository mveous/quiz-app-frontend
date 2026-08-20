import hashlib
import json
import re

from app.services.ai.prompts import EXPLANATION_TASK_MARKER, QUIZ_GENERATION_TASK_MARKER
from app.services.ai.provider import AIProvider

_MOCK_EXPLANATION = (
    "This answer is scored by similarity to the reference answer. Review the key "
    "concept behind the question and try to state it more precisely next time."
)


class MockAIProvider(AIProvider):
    """Deterministic, network-free provider used in tests and as a safe default
    when no self-hosted model is configured/reachable."""

    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.4,
        response_schema: dict | None = None,
    ) -> str:
        if QUIZ_GENERATION_TASK_MARKER in prompt:
            return self._mock_quiz_json(prompt)
        if EXPLANATION_TASK_MARKER in prompt:
            return _MOCK_EXPLANATION
        return ""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._pseudo_embedding(text) for text in texts]

    @staticmethod
    def _pseudo_embedding(text: str, dim: int = 768) -> list[float]:
        digest = hashlib.sha256(text.strip().lower().encode("utf-8")).digest()
        return [(digest[i % len(digest)] / 127.5) - 1.0 for i in range(dim)]

    @staticmethod
    def _mock_quiz_json(prompt: str) -> str:
        match = re.search(r"REQUEST_PARAMS: (\{.*\})", prompt)
        params = json.loads(match.group(1)) if match else {}
        question_count: int = params.get("question_count", 3)
        question_types: list[str] = params.get("question_types") or ["mcq"]
        difficulty: str = params.get("difficulty", "medium")

        questions = []
        for i in range(question_count):
            q_type = question_types[i % len(question_types)]
            questions.append(_mock_question(q_type, i + 1, difficulty))
        return json.dumps(questions)


def _mock_question(q_type: str, index: int, difficulty: str) -> dict:
    if q_type == "mcq":
        return {
            "type": "mcq",
            "prompt": f"Mock MCQ question {index}",
            "difficulty": difficulty,
            "explanation": "Option B is correct because it directly answers the mock prompt.",
            "options": [
                {"label": "A", "text": "Incorrect option A", "is_correct": False},
                {"label": "B", "text": "Correct option B", "is_correct": True},
                {"label": "C", "text": "Incorrect option C", "is_correct": False},
                {"label": "D", "text": "Incorrect option D", "is_correct": False},
            ],
            "correct_answer_text": None,
        }
    if q_type == "true_false":
        return {
            "type": "true_false",
            "prompt": f"Mock true/false statement {index}",
            "difficulty": difficulty,
            "explanation": "This statement is true in the mock dataset.",
            "options": [
                {"label": "True", "text": "True", "is_correct": True},
                {"label": "False", "text": "False", "is_correct": False},
            ],
            "correct_answer_text": None,
        }
    return {
        "type": "short_answer",
        "prompt": f"Mock short-answer question {index}",
        "difficulty": difficulty,
        "explanation": "The reference answer covers the core mock concept.",
        "options": None,
        "correct_answer_text": "mock reference answer",
    }
