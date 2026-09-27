from collections import deque
from typing import Any


class FakeLLM:
    def __init__(self, responses: list[Any]) -> None:
        # 测试会把预先创建好的 Pydantic 实例放进列表；deque 便于每次从左侧取一条。
        self.responses = deque(responses)

    def generate_structured(self, system_prompt: str, user_prompt: str, output_type: type[Any]):
        from mini_researcher.llm import LLMResult
        from mini_researcher.models import Usage

        if not self.responses:
            raise RuntimeError("No fake response configured")
        # 每调用一次 generate_structured，就取出一条预设响应；这里不会调用真实大模型。
        value = self.responses.popleft()
        # output_type 是调用方传入的真实类对象，例如 ResearchPlan 或 ReportDraft。
        # FakeLLM 不负责转换，只检查预设实例是否属于调用方要求的类型。
        if not isinstance(value, output_type):
            raise TypeError(f"Expected {output_type.__name__}, got {type(value).__name__}")
        # 和真实 LLM 保持同一种返回外壳：value 放业务结果，usage 放调用用量。
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
