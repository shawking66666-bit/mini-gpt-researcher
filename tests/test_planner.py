import pytest

from mini_researcher.models import ResearchPlan, ResearchQuestion
from mini_researcher.planner import Planner
from tests.fakes import FakeLLM


def test_planner_returns_four_unique_questions() -> None:
    sample_plan = ResearchPlan(
        topic="AI agents",
        questions=[
            ResearchQuestion(id=f"q{i}", text=f"research dimension {i}")
            for i in range(1, 5)
        ],
    )
    # 使用 FakeLLM 隔离真实 API，让测试结果固定且不消耗额度。
    planner = Planner(FakeLLM([sample_plan]))

    plan = planner.create_plan("AI agents")

    assert plan.topic == "AI agents"
    assert len(plan.questions) == 4
    assert len({question.text.casefold() for question in plan.questions}) == 4


def test_planner_rejects_plan_without_exactly_four_questions() -> None:
    short_plan = ResearchPlan(
        topic="AI agents",
        questions=[
            ResearchQuestion(id=f"q{i}", text=f"research dimension {i}")
            for i in range(1, 4)
        ],
    )
    planner = Planner(FakeLLM([short_plan]))

    with pytest.raises(ValueError, match="exactly four"):
        planner.create_plan("AI agents")


def test_planner_normalizes_question_whitespace() -> None:
    plan_with_extra_whitespace = ResearchPlan(
        topic="AI agents",
        questions=[
            ResearchQuestion(id="q1", text="  agent   context  "),
            ResearchQuestion(id="q2", text="market alternatives"),
            ResearchQuestion(id="q3", text="technical risks"),
            ResearchQuestion(id="q4", text="evaluation outcomes"),
        ],
    )
    planner = Planner(FakeLLM([plan_with_extra_whitespace]))

    plan = planner.create_plan("AI agents")

    assert plan.questions[0].text == "agent context"


def test_planner_rejects_duplicate_questions_after_normalization() -> None:
    duplicate_plan = ResearchPlan(
        topic="AI agents",
        questions=[
            ResearchQuestion(id="q1", text="AI agent risks"),
            ResearchQuestion(id="q2", text="  ai   AGENT risks  "),
            ResearchQuestion(id="q3", text="market alternatives"),
            ResearchQuestion(id="q4", text="evaluation outcomes"),
        ],
    )
    planner = Planner(FakeLLM([duplicate_plan]))

    with pytest.raises(ValueError, match="unique"):
        planner.create_plan("AI agents")
