from typing import Any

from mini_researcher.llm import LLMResult
from mini_researcher.models import (
    ReflectionResult,
    ResearchPlan,
    ResearchQuestion,
    SearchResult,
    TaskStatus,
    Usage,
)
from mini_researcher.orchestrator import ResearchOrchestrator
from mini_researcher.planner import Planner
from mini_researcher.reflector import Reflector
from mini_researcher.search import SearchError
from tests.fakes import FakeLLM, FakeSearch


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
