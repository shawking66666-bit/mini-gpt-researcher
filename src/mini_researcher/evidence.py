from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from mini_researcher.models import Evidence, ResearchQuestion, SearchResult


_TRACKING_PARAMETERS = {"fbclid", "gclid"}


class EvidenceManager:
    def __init__(self, max_sources: int) -> None:
        self.max_sources = max_sources
        self._evidence: list[Evidence] = []
        self._seen_urls: set[str] = set()

    def add(
        self,
        question: ResearchQuestion,
        results: list[SearchResult],
    ) -> list[Evidence]:
        added: list[Evidence] = []

        for result in results:
            # 上限针对整个研究任务的累计证据，不是单次搜索结果数量。
            if len(self._evidence) >= self.max_sources:
                break

            normalized_url = self._normalize_url(result.url)
            if normalized_url in self._seen_urls:
                continue

            evidence = Evidence(
                source_id=f"S{len(self._evidence) + 1}",
                question_id=question.id,
                title=result.title,
                url=normalized_url,
                content=result.content,
            )
            self._seen_urls.add(normalized_url)
            self._evidence.append(evidence)
            added.append(evidence)

        return added

    def all(self) -> list[Evidence]:
        # 返回列表副本，避免外部代码意外修改 Manager 内部保存的证据。
        return list(self._evidence)

    @staticmethod
    def _normalize_url(url: str) -> str:
        parts = urlsplit(url)
        query_items = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if not key.casefold().startswith("utm_")
            and key.casefold() not in _TRACKING_PARAMETERS
        ]
        # 网页片段和跟踪参数不代表不同内容，去除后再用于来源去重。
        return urlunsplit(
            (
                parts.scheme.casefold(),
                parts.netloc.casefold(),
                parts.path,
                urlencode(query_items),
                "",
            )
        )
