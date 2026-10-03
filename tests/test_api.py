from datetime import UTC, datetime

from fastapi.testclient import TestClient
import pytest

from mini_researcher.api import create_app
from mini_researcher.models import ResearchReport, ResearchState, TaskStatus
from mini_researcher.repository import ResearchRepository


class _FakeResearchService:
    """API测试只隔离外部研究流程，SQLite读写仍使用真实实现。"""

    def __init__(self, repository: ResearchRepository) -> None:
        self.repository = repository

    def create_research(self, topic: str) -> ResearchState:
        state = ResearchState(
            task_id="created-task",
            topic=topic,
            status=TaskStatus.PENDING,
            created_at=datetime(2026, 10, 3, 8, 0, tzinfo=UTC),
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
