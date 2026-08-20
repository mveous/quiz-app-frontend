import re

from app.models.enums import BloomLevel, QuestionType

# Deterministic keyword/verb classifier, not an AI call: no added generation latency
# or cost, no new mock-provider branch to maintain, and fully unit-testable. Ordered
# highest cognitive level first so a prompt mentioning multiple verbs (e.g. an
# "analyze and explain" question) is tagged at its highest-order level.
_VERB_LEVELS: list[tuple[BloomLevel, set[str]]] = [
    (BloomLevel.CREATE, {"design", "create", "formulate", "compose", "construct", "devise", "propose"}),
    (BloomLevel.EVALUATE, {"evaluate", "justify", "critique", "argue", "defend", "judge", "assess"}),
    (
        BloomLevel.ANALYZE,
        {"analyze", "differentiate", "compare", "contrast", "distinguish", "examine", "categorize"},
    ),
    (BloomLevel.APPLY, {"apply", "solve", "calculate", "demonstrate", "compute", "implement"}),
    (BloomLevel.UNDERSTAND, {"explain", "summarize", "describe", "interpret", "discuss", "classify"}),
    (BloomLevel.REMEMBER, {"define", "list", "identify", "name", "recall", "state", "label"}),
]

_TYPE_FALLBACK: dict[QuestionType, BloomLevel] = {
    QuestionType.MCQ: BloomLevel.UNDERSTAND,
    QuestionType.TRUE_FALSE: BloomLevel.REMEMBER,
    QuestionType.SHORT_ANSWER: BloomLevel.APPLY,
}

_WORD_RE = re.compile(r"[a-zA-Z']+")


def classify_bloom_level(question_prompt: str, question_type: QuestionType) -> BloomLevel:
    words = set(_WORD_RE.findall(question_prompt.lower()))
    for level, verbs in _VERB_LEVELS:
        if words & verbs:
            return level
    return _TYPE_FALLBACK[question_type]
