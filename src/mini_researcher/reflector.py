from mini_researcher.llm import LLMClient
from mini_researcher.models import (
    Evidence,
    ReflectionResult,
    ResearchPlan,
    ResearchQuestion,
    Usage,
)


class Reflector:
    def __init__(self, llm: LLMClient) -> None:
        # 和 Planner 一样只依赖统一接口，因此测试可注入 FakeLLM。
        self.llm = llm
        self.last_usage = Usage()

    def find_gaps(
        self,
        topic: str,
        plan: ResearchPlan,
        evidence: list[Evidence],
    ) -> list[ResearchQuestion]:
        evidence_catalog = "\n".join(
            f"[{item.source_id}] question={item.question_id}: {item.content}"
            for item in evidence
        )
        result = self.llm.generate_structured(
            system_prompt=(
                "Review the research plan and evidence for unresolved information gaps. "
                "Return zero to two focused follow-up questions. Return JSON only."
            ),
            user_prompt=(
                f"Research topic: {topic}\n"
                f"Research plan: {plan.model_dump_json()}\n"
                f"Evidence:\n{evidence_catalog or '(none)'}"
            ),
            output_type=ReflectionResult,
        )
        self.last_usage = result.usage

        # 第二轮编号由模型提供，但轮次由确定性代码强制设置，避免模型越界。
        return [
            question.model_copy(update={"round_number": 2})
            for question in result.value.questions
        ]
