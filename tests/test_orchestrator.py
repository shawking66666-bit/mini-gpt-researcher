from datetime import UTC, datetime
from typing import Any

from mini_researcher.llm import LLMResult
from mini_researcher.models import (
    ReflectionResult,
    DocumentResult,
    EvidenceSourceType,
    RetrievalMode,
    ResearchPlan,
    ResearchQuestion,
    ResearchState,
    SearchResult,
    TaskStatus,
    Usage,
)
from mini_researcher.orchestrator import ResearchOrchestrator
from mini_researcher.planner import Planner
from mini_researcher.reflector import Reflector
from mini_researcher.search import SearchError
from tests.fakes import FakeDocumentRetriever, FakeLLM, FakeSearch


class _FakeLLMWithUsage:
    """为用量累计测试返回指定业务结果和指定Usage。"""

    def __init__(self, value: Any, usage: Usage) -> None:
        self.value = value
        self.usage = usage

    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_type: type[Any],
    ) -> LLMResult[Any]:
        if not isinstance(self.value, output_type):
            raise TypeError(
                f"Expected {output_type.__name__}, got {type(self.value).__name__}"
            )
        return LLMResult(value=self.value, usage=self.usage)


def test_partial_search_failure_does_not_abort_research() -> None:
    plan = ResearchPlan(
        topic="AI agents",
        questions=[
            ResearchQuestion(id=f"q{number}", text=f"question {number}")
            for number in range(1, 5)
        ],
    )
    search = FakeSearch(
        {
            "question 1": [
                SearchResult(
                    title="Source 1",
                    url="https://example.com/1",
                    content="evidence 1",
                )
            ],
            "question 2": SearchError("temporary search failure"),
            "question 3": [
                SearchResult(
                    title="Source 3",
                    url="https://example.com/3",
                    content="evidence 3",
                )
            ],
            "question 4": [],
        }
    )
    orchestrator = ResearchOrchestrator(
        planner=Planner(FakeLLM([plan])),
        search=search,
        reflector=Reflector(FakeLLM([ReflectionResult()])),
        max_results_per_question=5,
        max_sources=12,
    )

    state = orchestrator.run("AI agents")

    assert state.status == TaskStatus.REPORTING
    assert state.round_number == 1
    assert [item.question_id for item in state.evidence] == ["q1", "q3"]
    assert len(state.errors) == 1
    assert "q2" in state.errors[0]
    assert state.usage.search_requests == 4


def test_orchestrator_runs_only_one_bounded_follow_up_round() -> None:
    plan = ResearchPlan(
        topic="AI agents",
        questions=[
            ResearchQuestion(id=f"q{number}", text=f"question {number}")
            for number in range(1, 5)
        ],
    )
    reflection = ReflectionResult(
        questions=[
            ResearchQuestion(id="q5", text="follow-up question 5"),
            ResearchQuestion(id="q6", text="follow-up question 6"),
        ]
    )
    search_results = {
        f"question {number}": [
            SearchResult(
                title=f"Source {number}",
                url=f"https://example.com/{number}",
                content=f"evidence {number}",
            )
        ]
        for number in range(1, 5)
    }
    search_results.update(
        {
            f"follow-up question {number}": [
                SearchResult(
                    title=f"Source {number}",
                    url=f"https://example.com/{number}",
                    content=f"evidence {number}",
                )
            ]
            for number in range(5, 7)
        }
    )
    orchestrator = ResearchOrchestrator(
        planner=Planner(FakeLLM([plan])),
        search=FakeSearch(search_results),
        reflector=Reflector(FakeLLM([reflection])),
        max_results_per_question=5,
        max_sources=12,
    )

    state = orchestrator.run("AI agents")

    assert state.round_number == 2
    assert state.usage.search_requests == 6
    assert state.usage.llm_requests == 2
    assert [item.question_id for item in state.evidence] == [
        "q1",
        "q2",
        "q3",
        "q4",
        "q5",
        "q6",
    ]


def test_orchestrator_applies_one_source_limit_across_both_rounds() -> None:
    plan = ResearchPlan(
        topic="AI agents",
        questions=[
            ResearchQuestion(id=f"q{number}", text=f"question {number}")
            for number in range(1, 5)
        ],
    )
    reflection = ReflectionResult(
        questions=[
            ResearchQuestion(id="q5", text="follow-up question 5"),
            ResearchQuestion(id="q6", text="follow-up question 6"),
        ]
    )
    search_results = {
        f"question {question_number}": [
            SearchResult(
                title=f"Source {question_number}-{result_number}",
                url=f"https://example.com/{question_number}-{result_number}",
                content=f"evidence {question_number}-{result_number}",
            )
            for result_number in range(1, 3)
        ]
        for question_number in range(1, 5)
    }
    search_results.update(
        {
            f"follow-up question {question_number}": [
                SearchResult(
                    title=f"Source {question_number}-{result_number}",
                    url=f"https://example.com/{question_number}-{result_number}",
                    content=f"evidence {question_number}-{result_number}",
                )
                for result_number in range(1, 4)
            ]
            for question_number in range(5, 7)
        }
    )
    orchestrator = ResearchOrchestrator(
        planner=Planner(FakeLLM([plan])),
        search=FakeSearch(search_results),
        reflector=Reflector(FakeLLM([reflection])),
        max_results_per_question=5,
        max_sources=12,
    )

    state = orchestrator.run("AI agents")

    assert len(state.evidence) == 12
    assert [item.source_id for item in state.evidence] == [
        f"S{number}" for number in range(1, 13)
    ]
    assert [item.question_id for item in state.evidence] == [
        "q1",
        "q1",
        "q2",
        "q2",
        "q3",
        "q3",
        "q4",
        "q4",
        "q5",
        "q5",
        "q5",
        "q6",
    ]
    assert state.usage.search_requests == 6


def test_orchestrator_accumulates_usage_from_planner_and_reflector() -> None:
    plan = ResearchPlan(
        topic="AI agents",
        questions=[
            ResearchQuestion(id=f"q{number}", text=f"question {number}")
            for number in range(1, 5)
        ],
    )
    planner_llm = _FakeLLMWithUsage(
        plan,
        Usage(llm_requests=1, input_tokens=100, output_tokens=30),
    )
    reflector_llm = _FakeLLMWithUsage(
        ReflectionResult(),
        Usage(llm_requests=1, input_tokens=80, output_tokens=20),
    )
    orchestrator = ResearchOrchestrator(
        planner=Planner(planner_llm),
        search=FakeSearch({}),
        reflector=Reflector(reflector_llm),
        max_results_per_question=5,
        max_sources=12,
    )

    state = orchestrator.run("AI agents")

    assert state.usage.llm_requests == 2
    assert state.usage.search_requests == 4
    assert state.usage.input_tokens == 180
    assert state.usage.output_tokens == 50


def test_orchestrator_accumulates_provider_credits_after_successful_searches() -> None:
    plan = ResearchPlan(
        topic="AI agents",
        questions=[
            ResearchQuestion(id=f"q{number}", text=f"question {number}")
            for number in range(1, 5)
        ],
    )
    search = FakeSearch({})
    search.credits_per_request = 1
    orchestrator = ResearchOrchestrator(
        planner=Planner(FakeLLM([plan])),
        search=search,
        reflector=Reflector(FakeLLM([ReflectionResult()])),
        max_results_per_question=5,
        max_sources=12,
    )

    state = orchestrator.run("AI agents")

    assert state.usage.search_requests == 4
    assert state.usage.tavily_credits == 4


def test_orchestrator_uses_service_created_state() -> None:
    """Service 先保存的任务 ID 应在研究过程和最终结果中保持一致。"""

    topic = "AI agents"
    plan = ResearchPlan(
        topic=topic,
        questions=[
            ResearchQuestion(id=f"q{number}", text=f"question {number}")
            for number in range(1, 5)
        ],
    )
    initial_state = ResearchState(
        task_id="service-task-1",
        topic=topic,
        status=TaskStatus.PENDING,
        created_at=datetime(2026, 10, 2, tzinfo=UTC),
    )
    orchestrator = ResearchOrchestrator(
        planner=Planner(FakeLLM([plan])),
        search=FakeSearch({}),
        reflector=Reflector(FakeLLM([ReflectionResult()])),
        max_results_per_question=5,
        max_sources=12,
    )

    result = orchestrator.run(topic, state=initial_state)

    assert result is initial_state
    assert result.task_id == "service-task-1"
    assert result.status == TaskStatus.REPORTING


def test_hybrid_mode_interleaves_sources_in_both_rounds() -> None:
    plan = ResearchPlan(topic="AI agents", questions=[ResearchQuestion(id=f"q{i}", text="first question" if i == 1 else f"empty question {i}") for i in range(1, 5)])
    reflection = ReflectionResult(questions=[ResearchQuestion(id="q5", text="second question")])
    search = FakeSearch({
        "first question": [SearchResult(title="W1", url="https://example.com/1", content="web one")],
        "second question": [SearchResult(title="W2", url="https://example.com/2", content="web two")],
    })
    documents = FakeDocumentRetriever({
        ("kb-test", "first question"): [DocumentResult(document_name="notes.md", content="doc one", chunk_index=0)],
        ("kb-test", "second question"): [DocumentResult(document_name="notes.md", content="doc two", chunk_index=1)],
    })
    state = ResearchState(task_id="hybrid-task", topic="AI agents", status=TaskStatus.PENDING,
                          created_at=datetime(2026, 10, 2, tzinfo=UTC),
                          retrieval_mode=RetrievalMode.HYBRID, knowledge_base_id="kb-test")
    orchestrator = ResearchOrchestrator(
        planner=Planner(FakeLLM([plan])), search=search,
        reflector=Reflector(FakeLLM([reflection])), max_results_per_question=5,
        max_sources=12, document_retriever=documents, rag_top_k=3,
    )

    result = orchestrator.run("AI agents", state=state)

    assert [item.source_id for item in result.evidence] == ["S1", "S2", "S3", "S4"]
    assert [item.source_type for item in result.evidence] == [EvidenceSourceType.WEB, EvidenceSourceType.DOCUMENT] * 2
    assert result.usage.search_requests == 5
    assert len(documents.calls) == 5


def test_document_mode_never_uses_web_search() -> None:
    plan = ResearchPlan(topic="AI agents", questions=[ResearchQuestion(id=f"q{i}", text="first question" if i == 1 else f"empty question {i}") for i in range(1, 5)])
    search = FakeSearch({"first question": SearchError("web must not run")})
    documents = FakeDocumentRetriever({("kb-test", "first question"): [DocumentResult(document_name="notes.md", content="doc", chunk_index=0)]})
    state = ResearchState(task_id="doc-task", topic="AI agents", status=TaskStatus.PENDING,
                          created_at=datetime(2026, 10, 2, tzinfo=UTC),
                          retrieval_mode=RetrievalMode.DOCUMENT, knowledge_base_id="kb-test")
    orchestrator = ResearchOrchestrator(Planner(FakeLLM([plan])), search,
                                        Reflector(FakeLLM([ReflectionResult()])),
                                        max_results_per_question=5, max_sources=12,
                                        document_retriever=documents, rag_top_k=3)
    result = orchestrator.run("AI agents", state=state)
    assert result.usage.search_requests == 0
    assert len(result.evidence) == 1
    assert result.errors == []


def test_hybrid_keeps_document_when_web_search_fails() -> None:
    plan = ResearchPlan(topic="AI agents", questions=[ResearchQuestion(id=f"q{i}", text="first question" if i == 1 else f"empty question {i}") for i in range(1, 5)])
    documents = FakeDocumentRetriever({("kb-test", "first question"): [DocumentResult(document_name="notes.md", content="doc", chunk_index=0)]})
    state = ResearchState(task_id="hybrid-task", topic="AI agents", status=TaskStatus.PENDING,
                          created_at=datetime(2026, 10, 2, tzinfo=UTC),
                          retrieval_mode=RetrievalMode.HYBRID, knowledge_base_id="kb-test")
    orchestrator = ResearchOrchestrator(Planner(FakeLLM([plan])),
        FakeSearch({"first question": SearchError("provider unavailable")}),
        Reflector(FakeLLM([ReflectionResult()])), max_results_per_question=5,
        max_sources=12, document_retriever=documents, rag_top_k=3)
    result = orchestrator.run("AI agents", state=state)
    assert [item.source_type for item in result.evidence] == [EvidenceSourceType.DOCUMENT]
    assert len(result.errors) == 1
