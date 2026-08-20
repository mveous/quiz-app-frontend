import asyncio
from pathlib import Path
from threading import Lock

from llama_cpp import Llama

from app.services.ai.provider import AIProvider


class ShaliProvider(AIProvider):
    """MveousQuiz's own in-process AI layer ("Shali v1").

    Runs open-weight GGUF models directly inside this Python process via
    llama-cpp-python — no separate model-serving app to install or keep
    running. Model instances are expensive to construct (seconds), so each
    is loaded once, lazily, on first use and reused for the life of the
    process (one FastAPI process, one Celery worker process).
    """

    def __init__(
        self,
        generation_model_path: str,
        embedding_model_path: str,
        n_gpu_layers: int = -1,
        n_ctx: int = 8192,
    ) -> None:
        self._generation_model_path = generation_model_path
        self._embedding_model_path = embedding_model_path
        self._n_gpu_layers = n_gpu_layers
        self._n_ctx = n_ctx
        self._generation_llm: Llama | None = None
        self._embedding_llm: Llama | None = None
        self._lock = Lock()

    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.4,
        response_schema: dict | None = None,
    ) -> str:
        return await asyncio.to_thread(
            self._generate_sync, prompt, max_tokens, temperature, response_schema
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._embed_sync, texts)

    def _generate_sync(
        self, prompt: str, max_tokens: int, temperature: float, response_schema: dict | None
    ) -> str:
        llm = self._get_generation_llm()
        # Grammar-constrained decoding: llama.cpp compiles the JSON Schema into a
        # GBNF grammar and rejects any token that would violate it, so the model
        # physically cannot emit malformed JSON or the wrong field types/enum
        # values. This removes most of the parse/validation retries we'd otherwise
        # need for a small local model.
        response_format = (
            {"type": "json_object", "schema": response_schema} if response_schema else None
        )
        result = llm.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format,
        )
        return result["choices"][0]["message"]["content"] or ""

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        llm = self._get_embedding_llm()
        result = llm.create_embedding(texts)
        return [item["embedding"] for item in result["data"]]

    def _get_generation_llm(self) -> Llama:
        if self._generation_llm is None:
            with self._lock:
                if self._generation_llm is None:
                    self._generation_llm = Llama(
                        model_path=self._resolve_path(self._generation_model_path),
                        n_gpu_layers=self._n_gpu_layers,
                        n_ctx=self._n_ctx,
                        verbose=False,
                    )
        return self._generation_llm

    def _get_embedding_llm(self) -> Llama:
        if self._embedding_llm is None:
            with self._lock:
                if self._embedding_llm is None:
                    self._embedding_llm = Llama(
                        model_path=self._resolve_path(self._embedding_model_path),
                        embedding=True,
                        n_gpu_layers=self._n_gpu_layers,
                        verbose=False,
                    )
        return self._embedding_llm

    @staticmethod
    def _resolve_path(path: str) -> str:
        candidate = Path(path)
        if candidate.is_absolute():
            return str(candidate)
        return str((Path(__file__).resolve().parents[4] / candidate).resolve())
