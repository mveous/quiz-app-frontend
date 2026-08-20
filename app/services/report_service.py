import uuid
from collections import defaultdict
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationFailedError
from app.models.attempt import QuizAttempt
from app.models.enums import AttemptStatus
from app.models.user import User
from app.repositories.attempt_repository import AttemptRepository
from app.repositories.quiz_repository import QuizRepository
from app.schemas.attempt import (
    AttemptReportOut,
    AttemptSummaryOut,
    BloomBreakdownOut,
    QuestionReportOut,
    TrendOut,
    TrendPointOut,
)
from app.services.report.exporters import render_csv, render_pdf

STRONG_ACCURACY_THRESHOLD = 0.75
WEAK_ACCURACY_THRESHOLD = 0.5
RECENT_ATTEMPTS_FOR_TREND = 5


class ReportService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._attempts = AttemptRepository(session)
        self._quizzes = QuizRepository(session)

    async def get_report(self, user: User, attempt_id: uuid.UUID) -> AttemptReportOut:
        attempt = await self._get_owned_attempt(user, attempt_id)
        if attempt.status != AttemptStatus.SUBMITTED:
            raise ValidationFailedError("Attempt has not been submitted yet")

        questions = await self._quizzes.list_questions(attempt.quiz_id)
        answers_by_question = {a.question_id: a for a in await self._attempts.list_answers(attempt.id)}
        options_by_question = await self._quizzes.list_options_for_questions(
            [q.id for q in questions]
        )

        question_reports: list[QuestionReportOut] = []
        band_correct: dict[str, int] = defaultdict(int)
        band_total: dict[str, int] = defaultdict(int)
        bloom_correct: dict[str, int] = defaultdict(int)
        bloom_total: dict[str, int] = defaultdict(int)

        for question in questions:
            answer = answers_by_question.get(question.id)
            band_total[question.difficulty.value] += 1
            if answer and answer.is_correct:
                band_correct[question.difficulty.value] += 1

            if question.bloom_level is not None:
                bloom_total[question.bloom_level.value] += 1
                if answer and answer.is_correct:
                    bloom_correct[question.bloom_level.value] += 1

            your_answer = answer.response_text if answer else None
            if your_answer is None and answer and answer.selected_option_id is not None:
                selected = next(
                    (
                        o
                        for o in options_by_question.get(question.id, [])
                        if o.id == answer.selected_option_id
                    ),
                    None,
                )
                your_answer = selected.text if selected else None

            question_reports.append(
                QuestionReportOut(
                    question_id=question.id,
                    prompt=question.prompt,
                    type=question.type.value,
                    difficulty=question.difficulty.value,
                    bloom_level=question.bloom_level.value if question.bloom_level else None,
                    your_answer=your_answer,
                    is_correct=answer.is_correct if answer else None,
                    marks_awarded=float(answer.marks_awarded)
                    if answer and answer.marks_awarded is not None
                    else None,
                    marks=float(question.marks),
                    explanation=question.explanation,
                    ai_feedback=answer.ai_feedback if answer else None,
                )
            )

        strong_bands = [
            band
            for band, total in band_total.items()
            if total and (band_correct[band] / total) >= STRONG_ACCURACY_THRESHOLD
        ]
        weak_bands = [
            band
            for band, total in band_total.items()
            if total and (band_correct[band] / total) < WEAK_ACCURACY_THRESHOLD
        ]
        bloom_breakdown = BloomBreakdownOut(
            **{
                level: round((bloom_correct[level] / total) * 100, 2)
                for level, total in bloom_total.items()
                if total
            }
        )

        total_marks = float(attempt.total_marks or 0)
        score = float(attempt.score or 0)
        accuracy = round((score / total_marks) * 100, 2) if total_marks else 0.0
        time_taken = (
            int((attempt.submitted_at - attempt.started_at).total_seconds())
            if attempt.submitted_at
            else None
        )

        trend = await self._build_trend(user, attempt.id, accuracy)

        return AttemptReportOut(
            id=attempt.id,
            quiz_id=attempt.quiz_id,
            status=attempt.status,
            score=score,
            total_marks=total_marks,
            accuracy=accuracy,
            time_taken_seconds=time_taken,
            questions=question_reports,
            strong_difficulty_bands=strong_bands,
            weak_difficulty_bands=weak_bands,
            bloom_breakdown=bloom_breakdown,
            trend=trend,
        )

    async def list_history(self, user: User) -> list[AttemptSummaryOut]:
        rows = await self._attempts.list_submitted_for_user(user.id)
        return [self._to_summary(attempt, title) for attempt, title in rows]

    async def export(
        self, user: User, attempt_id: uuid.UUID, export_format: Literal["pdf", "csv"]
    ) -> tuple[bytes, str, str]:
        report = await self.get_report(user, attempt_id)
        if export_format == "csv":
            return render_csv(report), "text/csv", f"report-{attempt_id}.csv"
        return render_pdf(report), "application/pdf", f"report-{attempt_id}.pdf"

    async def _build_trend(
        self, user: User, current_attempt_id: uuid.UUID, current_accuracy: float
    ) -> TrendOut:
        rows = await self._attempts.list_submitted_for_user(
            user.id, limit=RECENT_ATTEMPTS_FOR_TREND + 1
        )
        # Exclude the attempt this report is being generated for; keep the most
        # recent N prior submitted attempts.
        prior = [(a, t) for a, t in rows if a.id != current_attempt_id][:RECENT_ATTEMPTS_FOR_TREND]

        recent_points = [
            TrendPointOut(
                attempt_id=attempt.id,
                quiz_title=title,
                submitted_at=attempt.submitted_at,
                accuracy=self._attempt_accuracy(attempt),
            )
            for attempt, title in prior
        ]

        previous_accuracy = recent_points[0].accuracy if recent_points else None
        average_accuracy = (
            round(sum(p.accuracy for p in recent_points) / len(recent_points), 2)
            if recent_points
            else None
        )

        return TrendOut(
            previous_attempt_accuracy=previous_accuracy,
            average_recent_accuracy=average_accuracy,
            delta_vs_previous=(
                round(current_accuracy - previous_accuracy, 2)
                if previous_accuracy is not None
                else None
            ),
            delta_vs_average=(
                round(current_accuracy - average_accuracy, 2)
                if average_accuracy is not None
                else None
            ),
            recent_points=recent_points,
        )

    @staticmethod
    def _attempt_accuracy(attempt: QuizAttempt) -> float:
        total_marks = float(attempt.total_marks or 0)
        score = float(attempt.score or 0)
        return round((score / total_marks) * 100, 2) if total_marks else 0.0

    @classmethod
    def _to_summary(cls, attempt: QuizAttempt, title: str) -> AttemptSummaryOut:
        return AttemptSummaryOut(
            id=attempt.id,
            quiz_id=attempt.quiz_id,
            quiz_title=title,
            submitted_at=attempt.submitted_at,
            score=float(attempt.score or 0),
            total_marks=float(attempt.total_marks or 0),
            accuracy=cls._attempt_accuracy(attempt),
        )

    async def _get_owned_attempt(self, user: User, attempt_id: uuid.UUID) -> QuizAttempt:
        attempt = await self._attempts.get_by_id(attempt_id)
        if attempt is None:
            raise NotFoundError("Attempt not found")
        if attempt.user_id != user.id:
            raise ForbiddenError("You do not have access to this attempt")
        return attempt
