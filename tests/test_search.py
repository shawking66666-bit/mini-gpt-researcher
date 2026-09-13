from types import SimpleNamespace

import pytest

from mini_researcher.models import SearchResult
from mini_researcher.search import SearchError, TavilySearch
from tests.fakes import FakeSearch


def test_fake_search_returns_at_most_requested_results() -> None:
    first = SearchResult(title="A", url="https://a.test", content="one")
    second = SearchResult(title="B", url="https://b.test", content="two")
    search = FakeSearch({"agent": [first, second]})

    assert search.search("agent", max_results=1) == [first]


def test_fake_search_rejects_blank_query() -> None:
    with pytest.raises(ValueError, match="query must not be blank"):
        FakeSearch({}).search("  ", max_results=5)


class _FakeTavilyClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def search(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return {
            "results": [
                {
                    "title": "Tavily docs",
                    "url": "https://docs.tavily.com",
                    "content": "Official Tavily documentation.",
                    "score": 0.91,
                }
            ]
        }


def test_tavily_search_maps_provider_json_and_uses_basic_depth() -> None:
    client = _FakeTavilyClient()
    search = TavilySearch(client=client)

    results = search.search("Tavily Python SDK", max_results=5)

    assert results == [
        SearchResult(
            title="Tavily docs",
            url="https://docs.tavily.com",
            content="Official Tavily documentation.",
            score=0.91,
        )
    ]
    assert client.calls == [
        {
            "query": "Tavily Python SDK",
            "search_depth": "basic",
            "max_results": 5,
            "include_answer": False,
            "include_raw_content": False,
        }
    ]


def test_tavily_search_maps_provider_failure() -> None:
    class _FailingTavilyClient:
        def search(self, **kwargs: object) -> dict[str, object]:
            raise ConnectionError("secret provider detail")

    search = TavilySearch(client=_FailingTavilyClient())

    with pytest.raises(SearchError, match="Tavily search failed"):
        search.search("Tavily Python SDK", max_results=5)
