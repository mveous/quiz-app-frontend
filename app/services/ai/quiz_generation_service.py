import asyncio
import json
import logging
import re

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationFailedError
from app.models.enums import QuestionType
from app.models.quiz import Question, QuestionOption, Quiz
from app.schemas.ai_generation import GeneratedQuestion
from app.services.ai.bloom_classifier import classify_bloom_level
from app.services.ai.prompts import build_quiz_generation_prompt
from app.services.ai.provider import AIProvider
from app.services.ai.retrieval_service import RetrievalService
from app.services.ai.web_search_service import WebSearchService

logger = logging.getLogger("mveousquiz")

_QUESTIONS_ADAPTER = TypeAdapter(list[GeneratedQuestion])
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
# Smaller local models occasionally emit LaTeX-style backslashes (e.g. \times,
# \frac) despite being told not to, which json.loads rejects as invalid escapes.
# Escape any backslash that isn't already starting a valid JSON escape sequence.
_INVALID_JSON_ESCAPE_RE = re.compile(r'\\(?!["\\/bfnrtu])')
# Local 7B-class models occasionally hallucinate a malformed field (e.g. a
# duplicate "label" key instead of "text") on an otherwise-valid question.
# Re-sampling the same prompt usually produces a clean payload, so retry
# generation itself before giving up rather than failing on the first attempt.
_MAX_GENERATION_ATTEMPTS = 2
# Lower than the provider default: quiz questions are a factual-accuracy task,
# not a creative-writing one, and a more focused/deterministic sampling
# distribution measurably reduces hallucinated facts and answer-key mistakes.
_GENERATION_TEMPERATURE = 0.3


class QuizGenerationService:
    def __init__(self, session: AsyncSession, provider: AIProvider) -> None:
        self._session = session
        self._provider = provider

    async def generate_and_persist(self, quiz: Quiz) -> None:
        context_chunks = await self._gather_context(quiz)

        prompt = build_quiz_generation_prompt(
            topic=quiz.source_ref or quiz.title,
            question_count=quiz.question_count,
            difficulty=quiz.difficulty.value,
            question_types=quiz.question_types,
            context_chunks=context_chunks,
        )

        questions: list[GeneratedQuestion] | None = None
        last_error: ValidationFailedError | None = None
        response_schema = _QUESTIONS_ADAPTER.json_schema()
        for attempt in range(1, _MAX_GENERATION_ATTEMPTS + 1):
            raw_output = await self._provider.generate(
                prompt,
                temperature=_GENERATION_TEMPERATURE,
                response_schema=response_schema,
            )
            try:
                questions = self._parse_and_validate(raw_output)
                break
            except ValidationFailedError as exc:
                last_error = exc
                if attempt < _MAX_GENERATION_ATTEMPTS:
                    logger.warning(
                        "Quiz generation attempt %s/%s produced an invalid payload, retrying",
                        attempt,
                        _MAX_GENERATION_ATTEMPTS,
                    )
        if questions is None:
            assert last_error is not None
            raise last_error

        for order_index, generated in enumerate(questions):
            question = Question(
                quiz_id=quiz.id,
                type=generated.type,
                prompt=generated.prompt,
                explanation=generated.explanation,
                difficulty=generated.difficulty,
                order_index=order_index,
                correct_answer_text=generated.correct_answer_text,
                marks=1,
                bloom_level=classify_bloom_level(generated.prompt, generated.type),
            )
            self._session.add(question)
            await self._session.flush()

            for opt_index, option in enumerate(generated.options or []):
                self._session.add(
                    QuestionOption(
                        question_id=question.id,
                        label=option.label,
                        text=option.text,
                        is_correct=option.is_correct,
                        order_index=opt_index,
                    )
                )
        await self._session.flush()

    async def _gather_context(self, quiz: Quiz) -> list[str]:
        topic = quiz.source_ref or quiz.title
        tasks = []
        if quiz.use_my_documents:
            tasks.append(
                RetrievalService(self._session, self._provider).build_context(
                    quiz.owner_user_id, topic
                )
            )
        if quiz.use_web_search:
            tasks.append(WebSearchService().search_topic(topic))
        if not tasks:
            return []
        # Retrieval and web search don't depend on each other, so run them
        # concurrently instead of paying their latency twice in sequence.
        results = await asyncio.gather(*tasks)
        return [chunk for chunks in results for chunk in chunks]

    @staticmethod
    def _parse_and_validate(raw_output: str) -> list[GeneratedQuestion]:
        cleaned = _CODE_FENCE_RE.sub("", raw_output.strip())
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            try:
                # Retry once with stray backslashes escaped before giving up.
                payload = json.loads(_INVALID_JSON_ESCAPE_RE.sub(r"\\\\", cleaned))
            except json.JSONDecodeError as exc:
                logger.error("AI provider returned unparseable JSON: %r", raw_output)
                raise ValidationFailedError("AI provider returned an invalid quiz payload") from exc

        try:
            questions = _QUESTIONS_ADAPTER.validate_python(payload)
        except ValidationError as exc:
            logger.error("AI provider returned a payload that failed validation: %r", raw_output)
            raise ValidationFailedError("AI provider returned an invalid quiz payload") from exc

        for question in questions:
            _validate_question_shape(question)

        return questions


def _validate_question_shape(question: GeneratedQuestion) -> None:
    if question.type == QuestionType.MCQ:
        options = question.options or []
        if len(options) != 4 or sum(1 for o in options if o.is_correct) != 1:
            raise ValidationFailedError("MCQ question must have exactly 4 options with 1 correct")
    elif question.type == QuestionType.TRUE_FALSE:
        options = question.options or []
        if len(options) != 2 or sum(1 for o in options if o.is_correct) != 1:
            raise ValidationFailedError("True/false question must have exactly 2 options with 1 correct")
    elif question.type == QuestionType.SHORT_ANSWER:
        if not question.correct_answer_text:
            raise ValidationFailedError("Short-answer question must include a reference answer")
