from datetime import UTC, datetime
import sqlite3

import pytest

from mini_researcher.models import (
    Evidence,
    ResearchPlan,
    ResearchQuestion,
    ResearchReport,
    ResearchState,
    TaskStatus,
    Usage,
)
from mini_researcher.repository import ResearchRepository


def _sample_state() -> ResearchState:
    """构造一份包含嵌套对象的状态，验证SQLite读回后没有丢字段。"""

    return ResearchState(
        task_id="task-1",
        topic="AI agent evaluation",
        status=TaskStatus.REPORTING,
        created_at=datetime(2026, 9, 28, 8, 0, tzinfo=UTC),
        round_number=2,
        plan=ResearchPlan(
            topic="AI agent evaluation",
            questions=[
                ResearchQuestion(id="q1", text="What should be evaluated?")
            ],
        ),
        evidence=[
            Evidence(
                source_id="S1",
                question_id="q1",
                title="Evaluation guide",
                url="https://example.com/evaluation",
                content="Evaluate quality, cost, latency and safety.",
            )
        ],
        errors=["q2: search failed"],
        usage=Usage(llm_requests=2, search_requests=3, input_tokens=120),
    )


def test_repository_round_trips_state(tmp_path) -> None:
    """防止保存或读取时丢失ResearchState及其嵌套字段。"""

    repository = ResearchRepository(tmp_path / "research.db")
    repository.initialize()
    original = _sample_state()

    repository.save_state(original)
    loaded = repository.get_task(original.task_id)

    assert loaded == original
    assert loaded.evidence[0].source_id == "S1"


def test_repository_saves_report_for_existing_task(tmp_path) -> None:
    """防止最终报告没有关联并保存到所属研究任务。"""

    repository = ResearchRepository(tmp_path / "research.db")
    repository.initialize()
    state = _sample_state()
    report = ResearchReport(
        title="AI Agent Evaluation",
        markdown="Evidence-backed conclusion. [S1]",
        html="<p>Evidence-backed conclusion. [S1]</p>",
        used_source_ids=["S1"],
    )
    repository.save_state(state)

    repository.save_report(state.task_id, report)
    loaded = repository.get_task(state.task_id)

    assert loaded is not None
    assert loaded.report == report


def test_repository_lists_saved_tasks(tmp_path) -> None:
    """防止历史任务列表漏掉已经保存的研究任务。"""

    repository = ResearchRepository(tmp_path / "research.db")
    repository.initialize()
    first = _sample_state()
    second = first.model_copy(
        update={
            "task_id": "task-2",
            "topic": "AI agent observability",
        }
    )
    repository.save_state(first)
    repository.save_state(second)

    tasks = repository.list_tasks()

    assert len(tasks) == 2
    assert {task.task_id for task in tasks} == {"task-1", "task-2"}


def test_repository_rejects_report_without_parent_task(tmp_path) -> None:
    """外键应阻止报告指向不存在的研究任务。"""

    repository = ResearchRepository(tmp_path / "research.db")
    repository.initialize()
    report = ResearchReport(title="Orphan", markdown="No task exists.")

    with pytest.raises(sqlite3.IntegrityError):
        repository.save_report("missing-task", report)


def test_repository_rolls_back_incomplete_evidence_update(tmp_path) -> None:
    """一条证据写入失败时，任务状态和原有证据必须一起保持原状。"""

    repository = ResearchRepository(tmp_path / "research.db")
    repository.initialize()
    original = _sample_state()
    repository.save_state(original)
    invalid = original.model_copy(deep=True)
    invalid.status = TaskStatus.COMPLETED
    invalid.evidence.append(invalid.evidence[0].model_copy())

    with pytest.raises(sqlite3.IntegrityError):
        repository.save_state(invalid)

    assert repository.get_task(original.task_id) == original


def test_repository_saves_completed_state_with_report_together(tmp_path) -> None:
    """保存已完成状态时，最终报告也必须在同一保存操作中可读。"""

    repository = ResearchRepository(tmp_path / "research.db")
    repository.initialize()
    completed = _sample_state()
    completed.status = TaskStatus.COMPLETED
    completed.report = ResearchReport(
        title="Evaluation",
        markdown="Conclusion [S1]",
        used_source_ids=["S1"],
    )

    repository.save_state(completed)

    assert repository.get_task(completed.task_id) == completed
