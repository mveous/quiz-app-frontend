from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt import AttemptAnswer
from app.models.enums import QuestionType
from app.models.quiz import Question
from app.repositories.quiz_repository import QuizRepository
from app.services.ai.prompts import build_explanation_prompt
from app.services.ai.provider import AIProvider

SHORT_ANSWER_CORRECT_THRESHOLD = 0.6


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _keyword_overlap(reference: str, response: str) -> float:
    ref_words = {w.lower() for w in reference.split() if len(w) > 2}
    resp_words = {w.lower() for w in response.split() if len(w) > 2}
    if not ref_words:
        return 0.0
    return len(ref_words & resp_words) / len(ref_words)


class EvaluationService:
    """Always attaches an explanation to every evaluated answer, per CLAUDE.md's
    AI evaluation rule — MCQ/true-false reuse the question's authored explanation,
    short-answer gets a one-off AI-generated explanation."""

    def __init__(self, session: AsyncSession, provider: AIProvider) -> None:
        self._session = session
        self._provider = provider
        self._quizzes = QuizRepository(session)

    async def evaluate_answer(self, question: Question, answer: AttemptAnswer) -> None:
        if question.type in (QuestionType.MCQ, QuestionType.TRUE_FALSE):
            await self._evaluate_choice(question, answer)
        else:
            await self._evaluate_short_answer(question, answer)
        answer.evaluated_at = datetime.now(timezone.utc)

    async def _evaluate_choice(self, question: Question, answer: AttemptAnswer) -> None:
        options = await self._quizzes.list_options(question.id)
        correct_option = next((o for o in options if o.is_correct), None)
        is_correct = (
            correct_option is not None
            and answer.selected_option_id is not None
            and answer.selected_option_id == correct_option.id
        )
        answer.is_correct = is_correct
        answer.marks_awarded = float(question.marks) if is_correct else 0.0
        answer.ai_feedback = question.explanation

    async def _evaluate_short_answer(self, question: Question, answer: AttemptAnswer) -> None:
        reference = question.correct_answer_text or ""
        response = answer.response_text or ""

        if not response.strip():
            answer.is_correct = False
            answer.marks_awarded = 0.0
            answer.ai_feedback = "No answer was submitted."
            return

        reference_embedding, response_embedding = await self._provider.embed([reference, response])
        similarity = _cosine_similarity(reference_embedding, response_embedding)
        overlap = _keyword_overlap(reference, response)
        combined_score = min((0.7 * similarity) + (0.3 * overlap), 1.0)

        is_correct = combined_score >= SHORT_ANSWER_CORRECT_THRESHOLD
        full_marks = float(question.marks)
        answer.is_correct = is_correct
        answer.marks_awarded = full_marks if is_correct else round(full_marks * combined_score, 2)

        explanation_prompt = build_explanation_prompt(
            question_prompt=question.prompt,
            reference_answer=reference,
            student_answer=response,
            is_correct=is_correct,
        )
        answer.ai_feedback = await self._provider.generate(explanation_prompt)
