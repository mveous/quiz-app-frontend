from abc import ABC, abstractmethod


class AIProvider(ABC):
    """Provider-agnostic interface for LLM generation and embeddings.

    Swapping providers (self-hosted Ollama today; OpenAI/Claude/Gemini later)
    means adding one adapter class here — no call-site changes elsewhere.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.4,
        response_schema: dict | None = None,
    ) -> str:
        """Generate text from a prompt.

        response_schema, when given a JSON Schema dict, constrains decoding so the
        output is guaranteed to be syntactically valid JSON matching that schema
        (providers that can't enforce this natively should ignore it and rely on
        the caller's own parsing/validation as a fallback).
        """
        ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...
