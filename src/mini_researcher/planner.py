from mini_researcher.llm import LLMClient
from mini_researcher.models import ResearchPlan, Usage


class Planner:
    def __init__(self, llm: LLMClient) -> None:
        # Planner 只依赖统一接口，测试和真实运行可以分别注入 FakeLLM 与 DeepSeekLLM。
        self.llm = llm
        self.last_usage = Usage()

    def create_plan(self, topic: str) -> ResearchPlan:
        result = self.llm.generate_structured(
            system_prompt=(
                "Create a research plan with exactly four non-overlapping questions. "
                "Cover context, alternatives and evidence, constraints and risks, "
                "and evaluation and outcomes. Return JSON only."
            ),
            user_prompt=f"Research topic: {topic}",
            output_type=ResearchPlan,
        )
        self.last_usage = result.usage
        plan = result.value
        # ResearchPlan 允许 1～4 个问题；初始规划的业务规则要求必须恰好为 4 个。
        if len(plan.questions) != 4:
            raise ValueError("research plan must contain exactly four questions")

        # 合并连续空白，避免格式差异干扰后续的重复问题判断。
        normalized_questions = [
            question.model_copy(update={"text": " ".join(question.text.split())})
            for question in plan.questions
        ]

        # casefold() 让仅大小写不同的问题也被视为重复。
        unique_texts = {question.text.casefold() for question in normalized_questions}
        if len(unique_texts) != 4:
            raise ValueError("research plan must contain four unique questions")

        return plan.model_copy(update={"questions": normalized_questions})
