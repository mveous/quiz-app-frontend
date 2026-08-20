from functools import lru_cache

from app.core.config import settings
from app.services.ai.provider import AIProvider
from app.services.ai.providers.mock_provider import MockAIProvider
from app.services.ai.providers.ollama_provider import OllamaProvider
from app.services.ai.providers.shali_provider import ShaliProvider


@lru_cache
def get_ai_provider() -> AIProvider:
    if settings.ai_provider == "mock":
        return MockAIProvider()
    if settings.ai_provider == "shali":
        return ShaliProvider(
            generation_model_path=settings.shali_generation_model_path,
            embedding_model_path=settings.shali_embedding_model_path,
            n_gpu_layers=settings.shali_n_gpu_layers,
            n_ctx=settings.shali_n_ctx,
        )
    if settings.ai_provider == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            generation_model=settings.ollama_generation_model,
            embedding_model=settings.ollama_embedding_model,
        )
    raise ValueError(f"Unknown AI_PROVIDER: {settings.ai_provider}")
