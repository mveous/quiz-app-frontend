from app.models.enums import BloomLevel, QuestionType
from app.services.ai.bloom_classifier import classify_bloom_level


def test_remember_level_from_keyword():
    assert classify_bloom_level("Define photosynthesis.", QuestionType.SHORT_ANSWER) == BloomLevel.REMEMBER


def test_understand_level_from_keyword():
    assert (
        classify_bloom_level("Explain why the sky is blue.", QuestionType.SHORT_ANSWER)
        == BloomLevel.UNDERSTAND
    )


def test_apply_level_from_keyword():
    assert (
        classify_bloom_level("Calculate the area of the triangle.", QuestionType.SHORT_ANSWER)
        == BloomLevel.APPLY
    )


def test_analyze_level_from_keyword():
    assert (
        classify_bloom_level("Compare and contrast mitosis and meiosis.", QuestionType.SHORT_ANSWER)
        == BloomLevel.ANALYZE
    )


def test_evaluate_level_from_keyword():
    assert (
        classify_bloom_level("Justify your choice of algorithm.", QuestionType.SHORT_ANSWER)
        == BloomLevel.EVALUATE
    )


def test_create_level_from_keyword():
    assert (
        classify_bloom_level("Design a new experiment to test this hypothesis.", QuestionType.SHORT_ANSWER)
        == BloomLevel.CREATE
    )


def test_highest_order_verb_wins_when_multiple_present():
    # "analyze" (Analyze) and "explain" (Understand) both appear; Analyze must win.
    assert (
        classify_bloom_level("Analyze the data and explain your findings.", QuestionType.SHORT_ANSWER)
        == BloomLevel.ANALYZE
    )


def test_mcq_fallback_when_no_keyword_matches():
    assert classify_bloom_level("Which of the following is a mammal?", QuestionType.MCQ) == BloomLevel.UNDERSTAND


def test_true_false_fallback_when_no_keyword_matches():
    assert (
        classify_bloom_level("The Earth orbits the Sun.", QuestionType.TRUE_FALSE) == BloomLevel.REMEMBER
    )


def test_short_answer_fallback_when_no_keyword_matches():
    assert (
        classify_bloom_level("What is the capital of France?", QuestionType.SHORT_ANSWER)
        == BloomLevel.APPLY
    )
