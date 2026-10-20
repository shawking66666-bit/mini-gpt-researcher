from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from mini_researcher import api as api_module
from mini_researcher.api import create_app
from mini_researcher.knowledge import KnowledgeBaseSummary
from mini_researcher.models import ResearchReport, ResearchState, RetrievalMode, TaskStatus
from mini_researcher.repository import ResearchRepository


class _FakeResearchService:
    """API测试只隔离外部研究流程，SQLite读写仍使用真实实现。"""

    def __init__(self, repository: ResearchRepository) -> None:
        self.repository = repository
        self.calls = []

    def create_research(self, topic: str, retrieval_mode: RetrievalMode = RetrievalMode.WEB,
                        knowledge_base_id: str | None = None) -> ResearchState:
        self.calls.append((topic, retrieval_mode, knowledge_base_id))
        state = ResearchState(
            task_id="created-task",
            topic=topic,
            status=TaskStatus.PENDING,
            created_at=datetime(2026, 10, 3, 8, 0, tzinfo=UTC),
            retrieval_mode=retrieval_mode,
            knowledge_base_id=knowledge_base_id,
        )
        self.repository.save_state(state)
        return state


@pytest.fixture
def repository(tmp_path) -> ResearchRepository:
    repository = ResearchRepository(tmp_path / "research.db")
    repository.initialize()
    return repository


@pytest.fixture
def client(repository: ResearchRepository) -> TestClient:
    app = create_app(_FakeResearchService(repository), repository)
    return TestClient(app)


def _saved_state(
    repository: ResearchRepository,
    *,
    task_id: str = "saved-task",
    report: ResearchReport | None = None,
) -> ResearchState:
    state = ResearchState(
        task_id=task_id,
        topic="Saved research topic",
        status=TaskStatus.COMPLETED if report is not None else TaskStatus.REPORTING,
        created_at=datetime(2026, 10, 3, 9, 0, tzinfo=UTC),
        report=report,
    )
    repository.save_state(state)
    return state


def test_create_research_returns_created_task(client: TestClient) -> None:
    response = client.post("/research", json={"topic": "  AI agent delivery  "})

    assert response.status_code == 201
    assert response.json()["task_id"] == "created-task"
    assert response.json()["topic"] == "AI agent delivery"


def test_blank_topic_returns_422(client: TestClient) -> None:
    response = client.post("/research", json={"topic": "   "})

    assert response.status_code == 422


def test_missing_task_returns_404(client: TestClient) -> None:
    response = client.get("/research/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "research task not found"}


def test_get_task_returns_saved_state(
    client: TestClient,
    repository: ResearchRepository,
) -> None:
    original = _saved_state(repository)

    response = client.get(f"/research/{original.task_id}")

    assert response.status_code == 200
    assert response.json()["task_id"] == original.task_id
    assert response.json()["status"] == "reporting"


def test_report_endpoint_returns_report(
    client: TestClient,
    repository: ResearchRepository,
) -> None:
    report = ResearchReport(
        title="Agent Delivery",
        markdown="Verified conclusion.",
        html="<p>Verified conclusion.</p>",
    )
    state = _saved_state(repository, report=report)

    response = client.get(f"/research/{state.task_id}/report")

    assert response.status_code == 200
    assert response.json() == report.model_dump(mode="json")


def test_report_endpoint_returns_404_before_report_exists(
    client: TestClient,
    repository: ResearchRepository,
) -> None:
    state = _saved_state(repository)

    response = client.get(f"/research/{state.task_id}/report")

    assert response.status_code == 404
    assert response.json() == {"detail": "research report not found"}


def test_list_research_returns_saved_tasks(
    client: TestClient,
    repository: ResearchRepository,
) -> None:
    _saved_state(repository, task_id="task-1")
    _saved_state(repository, task_id="task-2")

    response = client.get("/research")

    assert response.status_code == 200
    assert {item["task_id"] for item in response.json()} == {"task-1", "task-2"}


def test_upload_returns_ready_knowledge_base(repository: ResearchRepository) -> None:
    class FakeKnowledgeService:
        def create(self, files):
            assert [(item.name, item.content) for item in files] == [("notes.md", b"hello")]
            return KnowledgeBaseSummary(knowledge_base_id="kb-test", document_count=1, chunk_count=1)

    client = TestClient(create_app(_FakeResearchService(repository), repository,
                                   knowledge_service=FakeKnowledgeService()))
    response = client.post("/knowledge-bases", files=[("files", ("notes.md", b"hello", "text/markdown"))])
    assert response.status_code == 201
    assert response.json() == {"knowledge_base_id": "kb-test", "document_count": 1,
                               "chunk_count": 1, "status": "ready"}


def test_hybrid_request_forwards_validated_knowledge_base(repository: ResearchRepository) -> None:
    service = _FakeResearchService(repository)
    client = TestClient(create_app(service, repository,
                                   knowledge_validator=lambda kb_id: kb_id == "kb-test"))
    response = client.post("/research", json={"topic": "AI agents", "retrieval_mode": "hybrid",
                                             "knowledge_base_id": "kb-test"})
    assert response.status_code == 201
    assert service.calls == [("AI agents", RetrievalMode.HYBRID, "kb-test")]


@pytest.mark.parametrize("body", [
    {"topic": "AI agents", "retrieval_mode": "document"},
    {"topic": "AI agents", "retrieval_mode": "hybrid", "knowledge_base_id": "missing"},
])
def test_document_research_rejects_missing_or_unready_id(repository: ResearchRepository, body) -> None:
    service = _FakeResearchService(repository)
    client = TestClient(create_app(service, repository, knowledge_validator=lambda _: False))
    response = client.post("/research", json=body)
    assert response.status_code == 422
    assert service.calls == []


def test_default_service_factory_returns_service_without_embedding_call(monkeypatch, repository) -> None:
    monkeypatch.setattr(api_module, "Settings", lambda: SimpleNamespace(
        deepseek_api_key="test", tavily_api_key="test",
        deepseek_base_url="https://api.deepseek.com", deepseek_model="test-model",
        max_results_per_question=5, max_final_sources=12, rag_top_k=3,
    ))
    monkeypatch.setattr(api_module, "_default_repository", lambda: repository)
    monkeypatch.setattr(api_module, "create_dashscope_embeddings",
                        lambda _: (_ for _ in ()).throw(AssertionError("embedding was initialized")))
    api_module._default_service.cache_clear()
    try:
        assert api_module._default_service() is not None
    finally:
        api_module._default_service.cache_clear()
