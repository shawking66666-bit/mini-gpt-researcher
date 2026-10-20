import re
from pathlib import Path
from typing import Callable, Protocol

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from mini_researcher.models import DocumentResult


class RetrievalError(RuntimeError):
    """不暴露底层向量库或供应商细节的文档检索错误。"""


class DocumentRetriever(Protocol):
    def retrieve(self, knowledge_base_id: str, query: str, top_k: int) -> list[DocumentResult]: ...


class ChromaDocumentRetriever:
    def __init__(
        self,
        knowledge_root: str | Path,
        embeddings: Embeddings,
        *,
        store_factory: Callable[..., Chroma] = Chroma,
    ) -> None:
        self.knowledge_root = Path(knowledge_root)
        self.embeddings = embeddings
        self.store_factory = store_factory

    def retrieve(self, knowledge_base_id: str, query: str, top_k: int) -> list[DocumentResult]:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", knowledge_base_id):
            raise ValueError("invalid knowledge_base_id")
        if not query.strip():
            raise ValueError("query must not be blank")
        if top_k < 1:
            raise ValueError("top_k must be positive")
        index_path = self.knowledge_root / knowledge_base_id / "index"
        if not index_path.is_dir():
            raise RetrievalError("knowledge-base index is not ready")
        try:
            store = self.store_factory(
                collection_name=f"kb_{knowledge_base_id}",
                persist_directory=str(index_path),
                embedding_function=self.embeddings,
            )
            matches = store.similarity_search_with_score(query, k=top_k)
            # LangChain Document 在此处转为项目自己的类型，后续模块不依赖 Chroma。
            return [
                DocumentResult(
                    document_name=doc.metadata["document_name"],
                    content=doc.page_content,
                    page_number=doc.metadata.get("page_number"),
                    chunk_index=doc.metadata["chunk_index"],
                    score=score,
                )
                for doc, score in matches
            ]
        except Exception as error:
            raise RetrievalError("document retrieval failed") from error
