import json

import pytest
from langchain_core.embeddings import Embeddings
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from mini_researcher.knowledge import KnowledgeBaseError, KnowledgeBaseService, UploadedDocument
from mini_researcher.retrieval import ChromaDocumentRetriever


class FakeIndex:
    def __init__(self):
        self.documents = []

    def add_documents(self, documents):
        self.documents.extend(documents)


def _service(tmp_path, *, store=None):
    store = store or FakeIndex()
    return KnowledgeBaseService(tmp_path / "knowledge_bases", object(),
                                store_factory=lambda **_: store), store


@pytest.mark.parametrize("files", [
    [UploadedDocument(name="bad.txt", content=b"text")],
    [UploadedDocument(name="../escape.md", content=b"text")],
    [UploadedDocument(name="/absolute.md", content=b"text")],
    [UploadedDocument(name="empty.md", content=b"")],
    [UploadedDocument(name="Same.md", content=b"one"), UploadedDocument(name="same.MD", content=b"two")],
    [UploadedDocument(name=f"{i}.md", content=b"a") for i in range(6)],
    [UploadedDocument(name="large.md", content=b"a" * (10 * 1024 * 1024 + 1))],
])
def test_create_rejects_invalid_files_before_writing(tmp_path, files) -> None:
    service, _ = _service(tmp_path)
    with pytest.raises(KnowledgeBaseError):
        service.create(files)
    assert not (tmp_path / "knowledge_bases").exists()


def test_markdown_ingestion_splits_and_publishes_ready_manifest(tmp_path) -> None:
    service, store = _service(tmp_path)
    summary = service.create([UploadedDocument(name="notes.md", content=("Agent architecture. " * 80).encode())])

    assert summary.status == "ready"
    assert summary.document_count == 1
    assert summary.chunk_count >= 2
    assert len(store.documents) == summary.chunk_count
    assert [doc.metadata["chunk_index"] for doc in store.documents] == list(range(summary.chunk_count))
    assert all(doc.metadata["document_name"] == "notes.md" for doc in store.documents)
    manifest = json.loads((tmp_path / "knowledge_bases" / summary.knowledge_base_id / "manifest.json").read_text())
    assert manifest["status"] == "ready"


def test_index_failure_does_not_publish_ready_knowledge_base(tmp_path) -> None:
    class BrokenIndex:
        def add_documents(self, documents):
            raise RuntimeError("private provider error")

    service, _ = _service(tmp_path, store=BrokenIndex())
    with pytest.raises(KnowledgeBaseError, match="indexing failed"):
        service.create([UploadedDocument(name="notes.md", content=b"Useful paragraph")])
    assert list((tmp_path / "knowledge_bases").rglob("manifest.json")) == []


def test_blank_extracted_text_does_not_publish_manifest(tmp_path) -> None:
    service, _ = _service(tmp_path)
    with pytest.raises(KnowledgeBaseError):
        service.create([UploadedDocument(name="notes.md", content=b"   \n")])
    assert list((tmp_path / "knowledge_bases").rglob("manifest.json")) == []


class _DeterministicEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] if "agent" in text.casefold() else [0.0, 1.0, 0.0]
                for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0] if "agent" in text.casefold() else [0.0, 1.0, 0.0]


def test_real_chroma_persists_and_reopens_with_fake_embeddings(tmp_path) -> None:
    root = tmp_path / "knowledge_bases"
    embeddings = _DeterministicEmbeddings()
    summary = KnowledgeBaseService(root, embeddings, embedding_dimension=3).create([
        UploadedDocument(name="notes.md", content=b"An agent plans and executes tasks."),
    ])
    results = ChromaDocumentRetriever(root, embeddings).retrieve(
        summary.knowledge_base_id, "agent", 3,
    )
    assert len(results) == 1
    assert results[0].document_name == "notes.md"
    assert "agent plans" in results[0].content


def test_pdf_ingestion_keeps_one_based_page_number(tmp_path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)}),
    })
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 72 720 Td (Agent guide content) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    with pdf_path.open("wb") as handle:
        writer.write(handle)

    service, store = _service(tmp_path)
    summary = service.create([UploadedDocument(name="sample.pdf", content=pdf_path.read_bytes())])
    assert summary.status == "ready"
    assert store.documents[0].metadata["page_number"] == 1
    assert "Agent guide content" in store.documents[0].page_content
