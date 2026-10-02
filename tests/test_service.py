from mini_researcher.models import (
    ReflectionResult,
    ResearchPlan,
    ResearchQuestion,
    SearchResult,
    TaskStatus,
)
from mini_researcher.orchestrator import ResearchOrchestrator
from mini_researcher.planner import Planner
from mini_researcher.reflector import Reflector
from mini_researcher.report import ReportDraft, ReportWriter
from mini_researcher.repository import ResearchRepository
from mini_researcher.service import ResearchService
from tests.fakes import FakeLLM, FakeSearch


class _RecordingRepository(ResearchRepository):
    """使用真实 SQLite，同时记录每次保存时的状态，核对业务流转。"""

    def __init__(self, database_path):
        super().__init__(database_path)
        self.saved_statuses: list[TaskStatus] = []

    def save_state(self, state):
        super().save_state(state)
        self.saved_statuses.append(state.status)


def _service(
    tmp_path,
    *,
    report_draft: ReportDraft,
    planner_available: bool = True,
    search_results: list[SearchResult] | None = None,
) -> tuple[ResearchService, _RecordingRepository]:
    topic = "AI agent evaluation"
    plan = ResearchPlan(
        topic=topic,
        questions=[
            ResearchQuestion(id=f"q{number}", text=f"question {number}")
            for number in range(1, 5)
        ],
    )
    orchestrator = ResearchOrchestrator(
        planner=Planner(FakeLLM([plan] if planner_available else [])),
        search=FakeSearch(
            {
                "question 1": search_results if search_results is not None else [
                    SearchResult(
                        title="Evaluation guide",
                        url="https://example.com/evaluation",
                        content="Measure quality, latency and cost.",
                    )
                ]
            }
        ),
        reflector=Reflector(FakeLLM([ReflectionResult()])),
        max_results_per_question=5,
        max_sources=12,
    )
    repository = _RecordingRepository(tmp_path / "research.db")
    repository.initialize()
    return (
        ResearchService(orchestrator, ReportWriter(FakeLLM([report_draft])), repository),
        repository,
    )


def test_service_saves_completed_report_and_usage(tmp_path) -> None:
    """完成一次研究后，数据库能读回同一任务的计划、证据、报告与累计用量。"""

    service, repository = _service(
        tmp_path,
        report_draft=ReportDraft(
            title="Evaluation",
            markdown="Quality matters. [S1]",
            used_source_ids=["S1"],
        ),
    )

    state = service.create_research("AI agent evaluation")
    saved = repository.get_task(state.task_id)

    assert state.status == TaskStatus.COMPLETED
    assert saved == state
    assert saved.report is not None
    assert saved.report.used_source_ids == ["S1"]
    assert saved.usage.llm_requests == 3
    assert saved.usage.search_requests == 4
    assert repository.saved_statuses == [
        TaskStatus.PENDING,
        TaskStatus.REPORTING,
        TaskStatus.COMPLETED,
    ]


def test_service_saves_failed_state_when_report_has_unknown_citation(tmp_path) -> None:
    """报告引用不存在的来源时，任务必须留下可查询的失败状态。"""

    service, repository = _service(
        tmp_path,
        report_draft=ReportDraft(
            title="Evaluation",
            markdown="Unsupported claim. [S9]",
            used_source_ids=["S9"],
        ),
    )

    state = service.create_research("AI agent evaluation")
    saved = repository.get_task(state.task_id)

    assert state.status == TaskStatus.FAILED
    assert saved == state
    assert saved.report is None
    assert saved.evidence[0].source_id == "S1"
    assert "InvalidCitationError" in saved.errors[-1]
    assert saved.usage.llm_requests == 3
    assert repository.saved_statuses[-1] == TaskStatus.FAILED


def test_service_rejects_blank_topic_before_creating_task(tmp_path) -> None:
    """空白主题不能创建数据库任务，也不能触发研究流程。"""

    service, repository = _service(
        tmp_path,
        report_draft=ReportDraft(title="Unused", markdown="Unused", used_source_ids=[]),
    )

    try:
        service.create_research("   ")
    except ValueError as error:
        assert "topic" in str(error)
    else:
        raise AssertionError("blank topic should be rejected")

    assert repository.list_tasks() == []


def test_service_saves_failed_state_when_planner_fails(tmp_path) -> None:
    """规划阶段失败也要保留同一个任务 ID 和可查询的失败状态。"""

    service, repository = _service(
        tmp_path,
        report_draft=ReportDraft(title="Unused", markdown="Unused"),
        planner_available=False,
    )

    state = service.create_research("AI agent evaluation")

    assert state.status == TaskStatus.FAILED
    assert repository.get_task(state.task_id) == state
    assert state.plan is None
    assert state.usage.llm_requests == 0
    assert "RuntimeError" in state.errors[-1]
    assert repository.saved_statuses == [TaskStatus.PENDING, TaskStatus.FAILED]


def test_service_completes_without_search_evidence(tmp_path) -> None:
    """零条搜索证据时，允许生成明确未引用来源的报告。"""

    service, repository = _service(
        tmp_path,
        report_draft=ReportDraft(
            title="No evidence",
            markdown="No verifiable sources were found.",
            used_source_ids=[],
        ),
        search_results=[],
    )

    state = service.create_research("AI agent evaluation")

    assert state.status == TaskStatus.COMPLETED
    assert state.evidence == []
    assert state.report is not None
    assert state.report.used_source_ids == []
    assert repository.get_task(state.task_id) == state
