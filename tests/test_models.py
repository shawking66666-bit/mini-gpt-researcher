from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from mini_researcher.models import (
    Evidence,
    EvidenceSourceType,
    DocumentResult,
    RetrievalMode,
    ResearchPlan,
    ResearchQuestion,
    ResearchState,
    SearchResult,
    TaskStatus,
    Usage,
)


def test_plan_accepts_four_initial_questions() -> None:
    questions = [
        ResearchQuestion(id=f"q{i}", text=f"research question {i}")
        for i in range(1, 5)
    ]

    plan = ResearchPlan(topic="AI agent evaluation", questions=questions)

    assert len(plan.questions) == 4
    assert plan.questions[0].round_number == 1


def test_plan_rejects_more_than_four_initial_questions() -> None:
    questions = [
        ResearchQuestion(id=f"q{i}", text=f"research question {i}")
        for i in range(1, 6)
    ]

    with pytest.raises(ValidationError):
        ResearchPlan(topic="AI agent evaluation", questions=questions)


def test_question_rejects_round_number_above_two() -> None:
    with pytest.raises(ValidationError):
        ResearchQuestion(id="q1", text="research question", round_number=3)


def test_search_result_rejects_non_http_url() -> None:
    with pytest.raises(ValidationError):
        SearchResult(title="Unsafe", url="file:///secret.txt", content="content")


def test_state_starts_with_empty_results() -> None:
    state = ResearchState(
        task_id="task-1",
        topic="AI agent evaluation",
        status=TaskStatus.PENDING,
        created_at=datetime(2026, 9, 12, tzinfo=UTC),
    )

    assert state.round_number == 0
    assert state.evidence == []
    assert state.errors == []
    assert state.usage.llm_requests == 0
    assert state.usage.search_requests == 0


def test_evidence_keeps_question_and_source_identity() -> None:
    evidence = Evidence(
        source_id="S1",
        question_id="q1",
        title="Official documentation",
        url="https://example.com/docs",
        content="Documented behavior.",
    )

    assert evidence.source_id == "S1"
    assert evidence.question_id == "q1"
    assert evidence.source_type == EvidenceSourceType.WEB


def test_document_evidence_requires_filename_but_not_url() -> None:
    evidence = Evidence(
        source_id="S2", question_id="q1", title="Handbook",
        source_type=EvidenceSourceType.DOCUMENT, document_name="handbook.pdf",
        page_number=12, chunk_index=0, content="Relevant paragraph.",
    )
    assert evidence.url is None
    assert evidence.document_name == "handbook.pdf"
    assert evidence.page_number == 12
    assert DocumentResult(document_name="notes.md", content="Text", chunk_index=0).page_number is None

    with pytest.raises(ValidationError):
        Evidence(source_id="S3", question_id="q1", title="Missing filename",
                 source_type=EvidenceSourceType.DOCUMENT, content="Text")

    with pytest.raises(ValidationError):
        Evidence(source_id="S4", question_id="q1", title="Missing URL", content="Text")


def test_state_defaults_to_web_mode_without_a_knowledge_base() -> None:
    state = ResearchState(task_id="task-1", topic="AI agent evaluation",
                          status=TaskStatus.PENDING, created_at=datetime(2026, 9, 12, tzinfo=UTC))
    assert state.retrieval_mode == RetrievalMode.WEB
    assert state.knowledge_base_id is None


def test_usage_accumulates_each_counter() -> None:
    """多个模块的请求、Token 与费用应进入同一任务总用量。"""

    total = Usage(llm_requests=2, search_requests=4, input_tokens=100)
    addition = Usage(
        llm_requests=1,
        search_requests=2,
        input_tokens=30,
        output_tokens=12,
        tavily_credits=3,
        estimated_cost_usd=0.02,
    )

    total.accumulate(addition)

    assert total == Usage(
        llm_requests=3,
        search_requests=6,
        input_tokens=130,
        output_tokens=12,
        tavily_credits=3,
        estimated_cost_usd=0.02,
    )
