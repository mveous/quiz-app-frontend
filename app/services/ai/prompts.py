import json

QUIZ_GENERATION_TASK_MARKER = "MVEOUSQUIZ_TASK: GENERATE_QUIZ_JSON"
EXPLANATION_TASK_MARKER = "MVEOUSQUIZ_TASK: EXPLAIN_ANSWER"


def build_quiz_generation_prompt(
    topic: str,
    question_count: int,
    difficulty: str,
    question_types: list[str],
    context_chunks: list[str] | None = None,
) -> str:
    params = json.dumps(
        {"question_count": question_count, "difficulty": difficulty, "question_types": question_types}
    )
    types_list = ", ".join(question_types)
    reference_section = _build_reference_section(context_chunks)
    return f"""{QUIZ_GENERATION_TASK_MARKER}
REQUEST_PARAMS: {params}

Role: You are an expert exam question author creating authentic practice questions.
Goal: Generate {question_count} exam-style practice questions about: {topic}
{reference_section}
Constraints:
- Difficulty: {difficulty}
- Question types to use, cycling through as appropriate: {types_list}
- Every question must include a clear explanation of the correct answer.
- "mcq" questions must have exactly 4 options with exactly one option marked correct.
- "true_false" questions must have exactly 2 options labeled "True" and "False".
- "short_answer" questions must omit options and instead provide a concise reference answer.
- Never invent unsafe, offensive, or biased content.
- Write all math in plain text, not LaTeX (e.g. "x^2 - 4 = 0", "3 times x = 12", "1/2") — never
  use backslash sequences like \\frac, \\times, \\(, or \\) anywhere in a string value.

Output format: Return ONLY a JSON array (no prose, no markdown fences). Each element must match:
{{
  "type": "mcq" | "true_false" | "short_answer",
  "prompt": string,
  "difficulty": "easy" | "medium" | "hard",
  "explanation": string,
  "options": [{{"label": string, "text": string, "is_correct": boolean}}] or null,
  "correct_answer_text": string or null
}}
"""


def _build_reference_section(context_chunks: list[str] | None) -> str:
    if not context_chunks:
        return ""
    joined = "\n---\n".join(context_chunks)
    return f"""
REFERENCE MATERIAL (from the student's own notes — use it to ground questions where
relevant, but do not fabricate facts beyond it):
{joined}
"""


def build_explanation_prompt(
    question_prompt: str, reference_answer: str, student_answer: str, is_correct: bool
) -> str:
    verdict = "correct" if is_correct else "incorrect"
    return f"""{EXPLANATION_TASK_MARKER}
Role: You are a supportive exam tutor giving feedback on a student's short-answer response.
Question: {question_prompt}
Reference answer: {reference_answer}
Student's answer: {student_answer}
The answer was judged: {verdict}.

Goal: Write a concise 2-3 sentence explanation of why the answer is {verdict} and name the key concept
being tested, so the student understands the reasoning, not just the verdict.

Output format: Plain text only, no JSON, no markdown.
"""
