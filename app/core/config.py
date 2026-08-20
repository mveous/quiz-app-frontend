from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "local"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    frontend_origin: str = "http://localhost:3000"

    database_url: str = "postgresql+asyncpg://mveousquiz:change-me-locally@localhost:5432/mveousquiz"

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    jwt_secret_key: str = "insecure-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    password_reset_token_expire_minutes: int = 30

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_email: str = "noreply@mveousquiz.local"
    smtp_from_name: str = "MveousQuiz"

    ai_provider: str = "shali"
    shali_generation_model_path: str = "models/Qwen2.5-7B-Instruct-Q4_K_M.gguf"
    shali_embedding_model_path: str = "models/nomic-embed-text-v1.5.Q4_K_M.gguf"
    shali_n_gpu_layers: int = -1
    shali_n_ctx: int = 8192
    ollama_base_url: str = "http://localhost:11434"
    ollama_generation_model: str = "llama3.1:8b"
    ollama_embedding_model: str = "nomic-embed-text"
    ai_embedding_dim: int = 768

    rate_limit_auth_per_minute: int = 10
    rate_limit_ai_generation_per_minute: int = 5
    rate_limit_document_upload_per_minute: int = 10

    document_max_file_size_mb: int = 5
    document_max_chars: int = 200_000
    rag_top_k: int = 5
    rag_max_context_chars: int = 6000

    web_search_enabled: bool = True
    web_search_max_articles: int = 2
    web_search_max_chars_per_article: int = 1500
    web_search_timeout_seconds: float = 8.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
