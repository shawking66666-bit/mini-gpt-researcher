from collections import deque
from typing import Any


class FakeLLM:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = deque(responses)

    def generate_structured(self, system_prompt: str, user_prompt: str, output_type: type[Any]):
        from mini_researcher.llm import LLMResult
        from mini_researcher.models import Usage

        if not self.responses:
            raise RuntimeError("No fake response configured")
        value = self.responses.popleft()
        if not isinstance(value, output_type):
            raise TypeError(f"Expected {output_type.__name__}, got {type(value).__name__}")
        return LLMResult(value=value, usage=Usage(llm_requests=1))


class FakeSearch:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses

    def search(self, query: str, max_results: int):
        if not query.strip():
            raise ValueError("query must not be blank")
        value = self.responses.get(query, [])
        if isinstance(value, Exception):
            raise value
        return list(value[:max_results])
