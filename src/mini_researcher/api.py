from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from mini_researcher.config import Settings
from mini_researcher.llm import DeepSeekLLM
from mini_researcher.models import ResearchReport, ResearchState
from mini_researcher.orchestrator import ResearchOrchestrator
from mini_researcher.planner import Planner
from mini_researcher.reflector import Reflector
from mini_researcher.report import ReportWriter
from mini_researcher.repository import ResearchRepository
from mini_researcher.search import TavilySearch
from mini_researcher.service import ResearchService


class ResearchCreateRequest(BaseModel):
    """POST /research 的 JSON 请求体。"""

    topic: str = Field(min_length=1)

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
    orchestrator = ResearchOrchestrator(
        planner=Planner(llm),
        search=TavilySearch(api_key=settings.tavily_api_key),
        reflector=Reflector(llm),
        max_results_per_question=settings.max_results_per_question,
        max_sources=settings.max_final_sources,
    )
    return ResearchService(
        orchestrator=orchestrator,
        report_writer=ReportWriter(llm),
        repository=_default_repository(),
    )


def create_app(
    service: ResearchService | None = None,
    repository: ResearchRepository | None = None,
) -> FastAPI:
    """创建API应用；传入依赖后可在测试中完全离线运行。"""

    api = FastAPI(title="Mini GPT Researcher", version="0.1.0")
    api.state.research_service = service
    api.state.research_repository = repository

    def get_repository(request: Request) -> ResearchRepository:
        # 测试使用注入的临时库；真实启动时才创建 data/research.db。
        return request.app.state.research_repository or _default_repository()

    def get_service(request: Request) -> ResearchService:
        # Service 只在 POST 真正执行研究时加载，因此 /docs 和查询接口不要求先读密钥。
        return request.app.state.research_service or _default_service()

    @api.post(
        "/research",
        response_model=ResearchState,
        status_code=status.HTTP_201_CREATED,
    )
    def create_research(payload: ResearchCreateRequest, request: Request) -> ResearchState:
        try:
            return get_service(request).create_research(payload.topic)
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
