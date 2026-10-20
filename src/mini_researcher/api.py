from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Callable

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field, field_validator

from mini_researcher.config import Settings
from mini_researcher.embedding import create_dashscope_embeddings
from mini_researcher.knowledge import KnowledgeBaseError, KnowledgeBaseService, KnowledgeBaseSummary, UploadedDocument
from mini_researcher.llm import DeepSeekLLM
from mini_researcher.models import ResearchReport, ResearchState, RetrievalMode
from mini_researcher.orchestrator import ResearchOrchestrator
from mini_researcher.planner import Planner
from mini_researcher.reflector import Reflector
from mini_researcher.report import ReportWriter
from mini_researcher.repository import ResearchRepository
from mini_researcher.retrieval import ChromaDocumentRetriever
from mini_researcher.search import TavilySearch
from mini_researcher.service import ResearchService


class ResearchCreateRequest(BaseModel):
    """POST /research 的 JSON 请求体。"""

    topic: str = Field(min_length=1)
    retrieval_mode: RetrievalMode = RetrievalMode.WEB
    knowledge_base_id: str | None = None

    @field_validator("topic", mode="before")
    @classmethod
    def strip_and_reject_blank_topic(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("topic must not be blank")
        return value


@lru_cache(maxsize=1)
def _default_repository() -> ResearchRepository:
    """首次访问接口时再创建本地数据库，导入API模块不会写硬盘。"""

    database_path = Path("data/research.db")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    repository = ResearchRepository(database_path)
    repository.initialize()
    return repository


@lru_cache(maxsize=1)
def _default_service() -> ResearchService:
    """使用环境配置组装真实研究流程；测试通过工厂注入假服务。"""

    settings = Settings()
    llm = DeepSeekLLM(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )
    class _LazyDocumentRetriever:
        def retrieve(self, knowledge_base_id: str, query: str, top_k: int):
            # 只有真正执行文档问题时才初始化 Embedding，纯联网模式不需要千问密钥。
            retriever = ChromaDocumentRetriever(
                Path("data/knowledge_bases"), create_dashscope_embeddings(settings),
            )
            return retriever.retrieve(knowledge_base_id, query, top_k)

    orchestrator = ResearchOrchestrator(
        planner=Planner(llm),
        search=TavilySearch(api_key=settings.tavily_api_key),
        reflector=Reflector(llm),
        max_results_per_question=settings.max_results_per_question,
        max_sources=settings.max_final_sources,
        document_retriever=_LazyDocumentRetriever(),
        rag_top_k=settings.rag_top_k,
    )
    return ResearchService(
        orchestrator=orchestrator,
        report_writer=ReportWriter(llm),
        repository=_default_repository(),
    )


def _default_knowledge_service() -> KnowledgeBaseService:
    settings = Settings()
    return KnowledgeBaseService(
        Path("data/knowledge_bases"), create_dashscope_embeddings(settings),
        chunk_size=settings.rag_chunk_size, chunk_overlap=settings.rag_chunk_overlap,
        embedding_model=settings.dashscope_embedding_model,
        embedding_dimension=settings.dashscope_embedding_dimension,
    )


def _knowledge_base_ready(knowledge_base_id: str) -> bool:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", knowledge_base_id):
        return False
    base = Path("data/knowledge_bases") / knowledge_base_id
    manifest_path = base / "manifest.json"
    if not (base / "index").is_dir() or not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        settings = Settings()
        return (manifest.get("status") == "ready"
                and manifest.get("embedding_model") == settings.dashscope_embedding_model
                and manifest.get("embedding_dimension") == settings.dashscope_embedding_dimension)
    except (OSError, ValueError):
        return False
def create_app(
    service: ResearchService | None = None,
    repository: ResearchRepository | None = None,
    knowledge_service: KnowledgeBaseService | None = None,
    knowledge_validator: Callable[[str], bool] | None = None,
) -> FastAPI:
    """创建API应用；传入依赖后可在测试中完全离线运行。"""

    api = FastAPI(title="Mini GPT Researcher", version="0.1.0")
    api.state.research_service = service
    api.state.research_repository = repository
    api.state.knowledge_service = knowledge_service
    api.state.knowledge_validator = knowledge_validator

    def get_repository(request: Request) -> ResearchRepository:
        # 测试使用注入的临时库；真实启动时才创建 data/research.db。
        return request.app.state.research_repository or _default_repository()

    def get_service(request: Request) -> ResearchService:
        # Service 只在 POST 真正执行研究时加载，因此 /docs 和查询接口不要求先读密钥。
        return request.app.state.research_service or _default_service()

    @api.post("/knowledge-bases", response_model=KnowledgeBaseSummary,
              status_code=status.HTTP_201_CREATED)
    async def create_knowledge_base(request: Request, files: list[UploadFile] = File(...)) -> KnowledgeBaseSummary:
        if not 1 <= len(files) <= 5:
            raise HTTPException(status_code=422, detail="upload requires 1 to 5 files")
        uploaded = []
        total_bytes = 0
        for file in files:
            content = await file.read(10 * 1024 * 1024 + 1)
            total_bytes += len(content)
            if len(content) > 10 * 1024 * 1024 or total_bytes > 30 * 1024 * 1024:
                raise HTTPException(status_code=422, detail="upload size limit exceeded")
            uploaded.append(UploadedDocument(name=file.filename or "", content=content))
        try:
            knowledge = request.app.state.knowledge_service or _default_knowledge_service()
            return knowledge.create(uploaded)
        except KnowledgeBaseError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=503, detail="knowledge-base service unavailable") from error

    @api.post(
        "/research",
        response_model=ResearchState,
        status_code=status.HTTP_201_CREATED,
    )
    def create_research(payload: ResearchCreateRequest, request: Request) -> ResearchState:
        if payload.retrieval_mode != RetrievalMode.WEB:
            if not payload.knowledge_base_id:
                raise HTTPException(status_code=422, detail="knowledge_base_id is required")
            validator = request.app.state.knowledge_validator or _knowledge_base_ready
            if not validator(payload.knowledge_base_id):
                raise HTTPException(status_code=422, detail="knowledge base is not ready")
        try:
            return get_service(request).create_research(
                payload.topic, payload.retrieval_mode, payload.knowledge_base_id,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            # API边界不向客户端暴露数据库、密钥或外部服务的内部堆栈。
            raise HTTPException(
                status_code=503,
                detail="research service unavailable",
            ) from error

    @api.get("/research", response_model=list[ResearchState])
    def list_research(request: Request) -> list[ResearchState]:
        try:
            return get_repository(request).list_tasks()
        except Exception as error:
            raise HTTPException(
                status_code=503,
                detail="research repository unavailable",
            ) from error

    @api.get("/research/{task_id}/report", response_model=ResearchReport)
    def get_report(task_id: str, request: Request) -> ResearchReport:
        try:
            state = get_repository(request).get_task(task_id)
        except Exception as error:
            raise HTTPException(
                status_code=503,
                detail="research repository unavailable",
            ) from error
        if state is None:
            raise HTTPException(status_code=404, detail="research task not found")
        if state.report is None:
            raise HTTPException(status_code=404, detail="research report not found")
        return state.report

    @api.get("/research/{task_id}", response_model=ResearchState)
    def get_research(task_id: str, request: Request) -> ResearchState:
        try:
            state = get_repository(request).get_task(task_id)
        except Exception as error:
            raise HTTPException(
                status_code=503,
                detail="research repository unavailable",
            ) from error
        if state is None:
            raise HTTPException(status_code=404, detail="research task not found")
        return state

    return api


app = create_app()
