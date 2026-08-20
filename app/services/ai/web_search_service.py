import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("mveousquiz")

_WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
_USER_AGENT = "MveousQuiz/1.0 (AI exam-prep platform, quiz question grounding; contact: mveousquiz-dev@example.com)"


class WebSearchService:
    """Grounds quiz generation in a free, no-API-key web knowledge source
    (Wikipedia) when the user gives a topic. Best-effort: any network or API
    failure degrades to an empty context list rather than failing quiz
    generation, matching RetrievalService's graceful-degradation contract."""

    async def search_topic(self, query: str, max_articles: int | None = None) -> list[str]:
        if not settings.web_search_enabled or not query.strip():
            return []

        limit = max_articles or settings.web_search_max_articles
        try:
            async with httpx.AsyncClient(
                timeout=settings.web_search_timeout_seconds, headers={"User-Agent": _USER_AGENT}
            ) as client:
                titles = await self._search_titles(client, query, limit)
                if not titles:
                    return []
                return await self._fetch_extracts(client, titles)
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning("Web search failed for topic %r: %s", query, exc)
            return []

    @staticmethod
    async def _search_titles(client: httpx.AsyncClient, query: str, limit: int) -> list[str]:
        response = await client.get(
            _WIKIPEDIA_API,
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "format": "json",
            },
        )
        response.raise_for_status()
        results = response.json()["query"]["search"]
        return [result["title"] for result in results[:limit]]

    @staticmethod
    async def _fetch_extracts(client: httpx.AsyncClient, titles: list[str]) -> list[str]:
        response = await client.get(
            _WIKIPEDIA_API,
            params={
                "action": "query",
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "titles": "|".join(titles),
                "format": "json",
            },
        )
        response.raise_for_status()
        pages = response.json()["query"]["pages"]

        extracts: list[str] = []
        for page in pages.values():
            text = (page.get("extract") or "").strip()
            title = page.get("title", "")
            if text:
                extracts.append(
                    f"From Wikipedia — {title}:\n{text[: settings.web_search_max_chars_per_article]}"
                )
        return extracts
