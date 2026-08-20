import enum


class UserRole(str, enum.Enum):
    STUDENT = "student"
    ADMIN = "admin"


class Difficulty(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuizSourceType(str, enum.Enum):
    TOPIC = "topic"
    TEXT = "text"


class QuizStatus(str, enum.Enum):
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class QuestionType(str, enum.Enum):
    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"


class AttemptStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"


class DocumentSourceType(str, enum.Enum):
    PASTED_TEXT = "pasted_text"
    TXT_UPLOAD = "txt_upload"
    PDF_UPLOAD = "pdf_upload"


class DocumentStatus(str, enum.Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class BloomLevel(str, enum.Enum):
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"
