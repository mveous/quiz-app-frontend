import httpx

from app.services.ai.provider import AIProvider


class OllamaProvider(AIProvider):
    """Self-hosted, provider-agnostic adapter talking to a local Ollama instance.

    No third-party API key required; run `ollama pull <model>` once locally
    (see README) before generation/embedding calls will succeed.
    """

    def __init__(self, base_url: str, generation_model: str, embedding_model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._generation_model = generation_model
        self._embedding_model = embedding_model

    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.4,
        response_schema: dict | None = None,
    ) -> str:
        payload = {
            "model": self._generation_model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }
        if response_schema is not None:
            # Ollama's structured-outputs mode: passing a JSON Schema here (rather
            # than the string "json") constrains decoding to that exact schema.
            payload["format"] = response_schema

        async with httpx.AsyncClient(base_url=self._base_url, timeout=180) as client:
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()
            return response.json()["response"]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        async with httpx.AsyncClient(base_url=self._base_url, timeout=60) as client:
            for text in texts:
                response = await client.post(
                    "/api/embeddings",
                    json={"model": self._embedding_model, "prompt": text},
                )
                response.raise_for_status()
                embeddings.append(response.json()["embedding"])
        return embeddings
