from datetime import datetime
from enum import StrEnum
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator


class TaskStatus(StrEnum):
    PENDING = "pending"
    PLANNING = "planning"
    RESEARCHING = "researching"
    REFLECTING = "reflecting"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"


class RetrievalMode(StrEnum):
    WEB = "web"
    DOCUMENT = "document"
    HYBRID = "hybrid"


class EvidenceSourceType(StrEnum):
    WEB = "web"
    DOCUMENT = "document"


class ResearchQuestion(BaseModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=3)
    round_number: int = Field(default=1, ge=1, le=2)


class ResearchPlan(BaseModel):
    topic: str = Field(min_length=3)
    questions: list[ResearchQuestion] = Field(min_length=1, max_length=4)


class ReflectionResult(BaseModel):
    # 空列表表示现有证据已经足够，不需要启动第二轮搜索。
    questions: list[ResearchQuestion] = Field(default_factory=list, max_length=2)


def _validate_http_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must use http or https")
    return value


class SearchResult(BaseModel):
    title: str = Field(min_length=1)
    url: str
    content: str
    score: float | None = None

    _http_url = field_validator("url")(_validate_http_url)


class DocumentResult(BaseModel):
    document_name: str = Field(min_length=1)
    content: str = Field(min_length=1)
    page_number: int | None = Field(default=None, ge=1)
    chunk_index: int = Field(ge=0)
    score: float | None = None


class Evidence(BaseModel):
    source_id: str = Field(pattern=r"^S[1-9]\d*$")
    question_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_type: EvidenceSourceType = EvidenceSourceType.WEB
    url: str | None = None
    document_name: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    chunk_index: int | None = Field(default=None, ge=0)
    content: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_source(self) -> "Evidence":
        if self.source_type == EvidenceSourceType.WEB:
            if self.url is None:
                raise ValueError("web evidence requires a URL")
            _validate_http_url(self.url)
        elif not self.document_name:
            raise ValueError("document evidence requires a document_name")
        return self


class Usage(BaseModel):
    llm_requests: int = Field(default=0, ge=0)
    search_requests: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    tavily_credits: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0)

    def accumulate(self, addition: "Usage") -> None:
        """将一次模块调用的请求数、Token和费用加到任务总用量中。"""

        self.llm_requests += addition.llm_requests
        self.search_requests += addition.search_requests
        self.input_tokens += addition.input_tokens
        self.output_tokens += addition.output_tokens
        self.tavily_credits += addition.tavily_credits
        self.estimated_cost_usd += addition.estimated_cost_usd


class ResearchReport(BaseModel):
    title: str = Field(min_length=1)
    markdown: str = Field(min_length=1)
    html: str | None = None
    used_source_ids: list[str] = Field(default_factory=list)


class ResearchState(BaseModel):
    task_id: str = Field(min_length=1)
    topic: str = Field(min_length=3)
    status: TaskStatus
    retrieval_mode: RetrievalMode = RetrievalMode.WEB
    knowledge_base_id: str | None = None
    created_at: datetime
    round_number: int = Field(default=0, ge=0, le=2)
    plan: ResearchPlan | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    report: ResearchReport | None = None
