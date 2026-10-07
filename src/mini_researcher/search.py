from typing import Any, Protocol

from mini_researcher.models import SearchResult


class SearchError(RuntimeError):
    """A provider-independent search failure."""


class SearchProvider(Protocol):
    credits_per_request: int

    def search(self, query: str, max_results: int) -> list[SearchResult]: ...


class TavilySearch:
    # Tavily basic search currently consumes one API credit after a successful request。
    credits_per_request = 1

    def __init__(
        self,
        client: Any | None = None,
        *,
        api_key: str | None = None,
    ) -> None:
        if client is None:
            if not api_key:
                raise ValueError("api_key is required when client is not provided")
            from tavily import TavilyClient

            client = TavilyClient(api_key=api_key)
        self.client = client

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        if not query.strip():
            raise ValueError("query must not be blank")
        try:
            response = self.client.search(
                query=query,
                search_depth="basic",
                max_results=max_results,
                include_answer=False,
                include_raw_content=False,
            )
            return [
                SearchResult(
                    title=item.get("title") or "Untitled source",
                    url=item["url"],
                    content=item.get("content") or "",
                    score=item.get("score"),
                )
                for item in response.get("results", [])
            ]
        except (ValueError, KeyError):
            raise
        except Exception as error:
            raise SearchError("Tavily search failed") from error
