from mini_researcher.models import (
    Evidence,
    ReflectionResult,
    ResearchPlan,
    ResearchQuestion,
)
from mini_researcher.reflector import Reflector
from tests.fakes import FakeLLM


def test_reflector_returns_at_most_two_round_two_questions() -> None:
    plan = ResearchPlan(
        topic="AI agents",
        questions=[
            ResearchQuestion(id=f"q{number}", text=f"initial question {number}")
            for number in range(1, 5)
        ],
    )
    evidence = [
        Evidence(
            source_id="S1",
            question_id="q1",
            title="Agent overview",
            url="https://example.com/agents",
            content="An overview of agent systems.",
        )
    ]
    reflection = ReflectionResult(
        questions=[
            ResearchQuestion(id="q5", text="Which evaluation gaps remain?"),
            ResearchQuestion(id="q6", text="Which operational risks remain?"),
        ]
    )
    reflector = Reflector(FakeLLM([reflection]))

    questions = reflector.find_gaps("AI agents", plan, evidence)

    assert [question.id for question in questions] == ["q5", "q6"]
    assert all(question.round_number == 2 for question in questions)


def test_reflector_returns_empty_list_when_no_gaps_remain() -> None:
    plan = ResearchPlan(
        topic="AI agents",
        questions=[
            ResearchQuestion(id=f"q{number}", text=f"initial question {number}")
            for number in range(1, 5)
        ],
    )
    reflector = Reflector(FakeLLM([ReflectionResult()]))

    questions = reflector.find_gaps("AI agents", plan, [])

    assert questions == []
