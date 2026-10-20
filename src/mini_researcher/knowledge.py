import json
import os
import re
from pathlib import Path
from typing import Callable
from uuid import uuid4

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field


MAX_FILES = 5
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 30 * 1024 * 1024
SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]


class KnowledgeBaseError(ValueError):
    """上传、解析或索引失败；不给调用方泄漏私有文件与供应商异常。"""


class UploadedDocument(BaseModel):
    name: str
    content: bytes


class KnowledgeBaseSummary(BaseModel):
    knowledge_base_id: str
    document_count: int = Field(ge=1)
    chunk_count: int = Field(ge=1)
    status: str = "ready"


class KnowledgeBaseService:
    def __init__(
        self,
        knowledge_root: str | Path,
        embeddings: Embeddings,
        *,
        store_factory: Callable[..., Chroma] = Chroma,
        chunk_size: int = 800,
        chunk_overlap: int = 120,
        embedding_model: str = "qwen3.7-text-embedding-flash",
        embedding_dimension: int = 1024,
    ) -> None:
        self.knowledge_root = Path(knowledge_root)
        self.embeddings = embeddings
        self.store_factory = store_factory
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_model = embedding_model
        self.embedding_dimension = embedding_dimension

    def create(self, files: list[UploadedDocument]) -> KnowledgeBaseSummary:
        self._validate_files(files)
        knowledge_base_id = uuid4().hex
        base = self.knowledge_root / knowledge_base_id
        document_dir = base / "documents"
        index_dir = base / "index"
        try:
            document_dir.mkdir(parents=True)
            index_dir.mkdir()
            documents = []
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=SEPARATORS,
            )
            for uploaded in files:
                path = document_dir / uploaded.name
                path.write_bytes(uploaded.content)
                if path.suffix.casefold() == ".pdf":
                    pages = PyPDFLoader(str(path)).load()
                else:
                    pages = TextLoader(str(path), encoding="utf-8").load()
                if not pages or not any(page.page_content.strip() for page in pages):
                    raise KnowledgeBaseError(f"no extractable text in {uploaded.name}")
                chunk_index = 0
                for page in pages:
                    for chunk in splitter.split_documents([page]):
                        if not chunk.page_content.strip():
                            continue
                        # PyPDFLoader 的 page 从 0 开始；对用户展示时用从 1 开始的页码。
                        page_number = page.metadata.get("page")
                        chunk.metadata = {
                            "document_name": uploaded.name,
                            "chunk_index": chunk_index,
                            **({"page_number": page_number + 1} if page_number is not None else {}),
                        }
                        documents.append(chunk)
                        chunk_index += 1
            if not documents:
                raise KnowledgeBaseError("documents contain no extractable text")
            store = self.store_factory(
                collection_name=f"kb_{knowledge_base_id}",
                persist_directory=str(index_dir),
                embedding_function=self.embeddings,
            )
            store.add_documents(documents)
            manifest = {
                "status": "ready",
                "knowledge_base_id": knowledge_base_id,
                "embedding_model": self.embedding_model,
                "embedding_dimension": self.embedding_dimension,
                "document_count": len(files),
                "chunk_count": len(documents),
                "files": [file.name for file in files],
            }
            pending = base / "manifest.pending.json"
            pending.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            # 只有全部索引成功后才发布 ready 清单；失败目录保留隔离，不自动删除用户数据。
            os.replace(pending, base / "manifest.json")
            return KnowledgeBaseSummary(
                knowledge_base_id=knowledge_base_id,
                document_count=len(files), chunk_count=len(documents),
            )
        except KnowledgeBaseError:
            raise
        except Exception as error:
            raise KnowledgeBaseError("knowledge-base indexing failed") from error

    @staticmethod
    def _validate_files(files: list[UploadedDocument]) -> None:
        if not 1 <= len(files) <= MAX_FILES:
            raise KnowledgeBaseError("upload requires 1 to 5 files")
        if sum(len(file.content) for file in files) > MAX_TOTAL_BYTES:
            raise KnowledgeBaseError("total upload exceeds 30 MiB")
        seen: set[str] = set()
        for file in files:
            # 路径、盘符和控制字符一律拒绝，绝不把客户端文件名当作任意写入路径。
            if (not re.fullmatch(r"[^\\/:*?\"<>|\x00-\x1f]+", file.name)
                    or file.name in {".", ".."}
                    or Path(file.name).suffix.casefold() not in {".pdf", ".md"}):
                raise KnowledgeBaseError("unsupported or unsafe filename")
            if not file.content or len(file.content) > MAX_FILE_BYTES:
                raise KnowledgeBaseError(f"invalid file size: {file.name}")
            normalized = file.name.casefold()
            if normalized in seen:
                raise KnowledgeBaseError("duplicate filename")
            seen.add(normalized)
