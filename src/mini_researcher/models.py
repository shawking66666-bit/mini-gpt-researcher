from datetime import datetime
from enum import StrEnum
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class TaskStatus(StrEnum):
    PENDING = "pending"
    PLANNING = "planning"
    RESEARCHING = "researching"
    REFLECTING = "reflecting"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"


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


class Evidence(BaseModel):
    source_id: str = Field(pattern=r"^S[1-9]\d*$")
    question_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: str
    content: str = Field(min_length=1)

    _http_url = field_validator("url")(_validate_http_url)


class Usage(BaseModel):
    llm_requests: int = Field(default=0, ge=0)
    search_requests: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    tavily_credits: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0)


class ResearchReport(BaseModel):
    title: str = Field(min_length=1)
    markdown: str = Field(min_length=1)
    html: str | None = None
    used_source_ids: list[str] = Field(default_factory=list)


class ResearchState(BaseModel):
    task_id: str = Field(min_length=1)
    topic: str = Field(min_length=3)
    status: TaskStatus
    created_at: datetime
    round_number: int = Field(default=0, ge=0, le=2)
    plan: ResearchPlan | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    report: ResearchReport | None = None
