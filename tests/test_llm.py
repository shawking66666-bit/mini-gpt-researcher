from types import SimpleNamespace

import pytest

from mini_researcher.llm import DeepSeekLLM, LLMError
from mini_researcher.models import ResearchPlan, ResearchQuestion
from tests.fakes import FakeLLM


def _plan() -> ResearchPlan:
    return ResearchPlan(
        topic="AI agents",
        questions=[
            ResearchQuestion(id=f"q{i}", text=f"research question {i}")
            for i in range(1, 5)
        ],
    )


def test_fake_llm_returns_next_typed_response() -> None:
    expected = _plan()
    llm = FakeLLM([expected])

    result = llm.generate_structured("Return JSON.", "Research AI agents.", ResearchPlan)

    assert result.value == expected
    assert result.usage.llm_requests == 1


def test_fake_llm_fails_when_responses_are_exhausted() -> None:
    llm = FakeLLM([])

    with pytest.raises(RuntimeError, match="No fake response configured"):
        llm.generate_structured("Return JSON.", "Research AI agents.", ResearchPlan)


class _FakeCompletions:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self.response


def test_deepseek_llm_requests_json_and_validates_response() -> None:
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=_plan().model_dump_json()))],
        usage=SimpleNamespace(prompt_tokens=120, completion_tokens=80),
    )
    completions = _FakeCompletions(response)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    llm = DeepSeekLLM(client=client, model="deepseek-v4-flash")

    result = llm.generate_structured(
        "Return a JSON research plan.",
        "Research AI agents.",
        ResearchPlan,
    )

    assert result.value == _plan()
    assert result.usage.input_tokens == 120
    assert result.usage.output_tokens == 80
    assert len(completions.calls) == 1
    assert completions.calls[0]["model"] == "deepseek-v4-flash"
    assert completions.calls[0]["messages"][1] == {
        "role": "user",
        "content": "Research AI agents.",
    }
    assert completions.calls[0]["response_format"] == {"type": "json_object"}
    assert completions.calls[0]["extra_body"] == {"thinking": {"type": "disabled"}}


def test_deepseek_llm_tells_provider_the_exact_top_level_schema() -> None:
    """真实模型不能自行增加research_plan等顶层包装字段。"""

    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=_plan().model_dump_json()))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )
    completions = _FakeCompletions(response)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    DeepSeekLLM(client=client).generate_structured(
        "Return JSON.",
        "Research AI agents.",
        ResearchPlan,
    )

    system_message = completions.calls[0]["messages"][0]["content"]
    assert '"topic"' in system_message
    assert '"questions"' in system_message
    assert "Do not wrap the object" in system_message


def test_deepseek_llm_rejects_empty_content() -> None:
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=""))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=0),
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=_FakeCompletions(response))
    )
    llm = DeepSeekLLM(client=client, model="deepseek-v4-flash")

    with pytest.raises(ValueError, match="empty content"):
        llm.generate_structured("Return JSON.", "Research agents.", ResearchPlan)


class _SequentialCompletions:
    def __init__(self, responses: list[object]) -> None:
        self.responses = iter(responses)
        self.call_count = 0

    def create(self, **kwargs: object) -> object:
        self.call_count += 1
        return next(self.responses)


def test_deepseek_llm_retries_invalid_json_once() -> None:
    invalid = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=2),
    )
    valid = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=_plan().model_dump_json()))],
        usage=SimpleNamespace(prompt_tokens=20, completion_tokens=10),
    )
    completions = _SequentialCompletions([invalid, valid])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    llm = DeepSeekLLM(client=client)

    result = llm.generate_structured("Return JSON.", "Research agents.", ResearchPlan)

    assert result.value == _plan()
    assert completions.call_count == 2
    assert result.usage.llm_requests == 2


def test_deepseek_llm_maps_provider_failure() -> None:
    class _FailingCompletions:
        def create(self, **kwargs: object) -> object:
            raise ConnectionError("secret provider detail")

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=_FailingCompletions())
    )
    llm = DeepSeekLLM(client=client)

    with pytest.raises(LLMError, match="DeepSeek request failed"):
        llm.generate_structured("Return JSON.", "Research agents.", ResearchPlan)
