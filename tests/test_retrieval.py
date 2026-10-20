from pathlib import Path
import json

import pytest
from langchain_core.documents import Document

from mini_researcher.retrieval import ChromaDocumentRetriever, RetrievalError
from tests.fakes import FakeDocumentRetriever


class _FakeChroma:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def similarity_search_with_score(self, query: str, k: int):
        self.calls.append((query, k))
        return self.results


def test_chroma_retriever_converts_documents_and_forwards_top_k(tmp_path: Path) -> None:
    index = tmp_path / "data" / "knowledge_bases" / "kb-test" / "index"
    index.mkdir(parents=True)
    (index.parent / "manifest.json").write_text(json.dumps({"status": "ready"}))
    fake_store = _FakeChroma([(Document(page_content="paragraph", metadata={"document_name": "handbook.pdf", "page_number": 12, "chunk_index": 0}), 0.25)])
    retriever = ChromaDocumentRetriever(tmp_path / "data" / "knowledge_bases", object(),
                                         store_factory=lambda **_: fake_store)

    results = retriever.retrieve("kb-test", "AI agents", 3)

    assert fake_store.calls == [("AI agents", 3)]
    assert results[0].document_name == "handbook.pdf"
    assert results[0].page_number == 12
    assert results[0].score == 0.25


def test_chroma_retriever_rejects_missing_index_and_bad_input(tmp_path: Path) -> None:
    retriever = ChromaDocumentRetriever(tmp_path, object(), store_factory=lambda **_: _FakeChroma([]))
    with pytest.raises(RetrievalError):
        retriever.retrieve("missing", "question", 3)
    with pytest.raises(ValueError):
        retriever.retrieve("../escape", "question", 3)
    with pytest.raises(ValueError):
        retriever.retrieve("missing", " ", 3)


def test_chroma_retriever_rejects_unpublished_partial_index(tmp_path: Path) -> None:
    (tmp_path / "kb-partial" / "index").mkdir(parents=True)
    retriever = ChromaDocumentRetriever(tmp_path, object(), store_factory=lambda **_: _FakeChroma([]))
    with pytest.raises(RetrievalError, match="not ready"):
        retriever.retrieve("kb-partial", "question", 3)


def test_fake_document_retriever_records_lookup() -> None:
    fake = FakeDocumentRetriever({("kb-test", "question"): []})
    assert fake.retrieve("kb-test", "question", 3) == []
    assert fake.calls == [("kb-test", "question", 3)]
