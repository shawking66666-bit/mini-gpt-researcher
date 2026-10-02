import re

from markdown_it import MarkdownIt
from pydantic import BaseModel, Field

from mini_researcher.llm import LLMClient
from mini_researcher.models import Evidence, ResearchPlan, ResearchReport, Usage


_CITATION_PATTERN = re.compile(r"\[(S\d+)\]")


class InvalidCitationError(ValueError):
    """报告引用了证据目录中不存在的来源。"""


class ReportDraft(BaseModel):
    """LLM生成的结构化报告草稿；引用校验通过后才能成为正式报告。"""

    title: str = Field(min_length=1)
    markdown: str = Field(min_length=1)
    used_source_ids: list[str] = Field(default_factory=list)


def render_html(markdown_text: str) -> str:
    """将Markdown渲染成HTML，同时把模型输出的原始HTML当作普通文本。"""

    renderer = MarkdownIt("commonmark", {"html": False})
    return renderer.render(markdown_text)


class ReportWriter:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm
        self.last_usage = Usage()

    def write(
        self,
        topic: str,
        plan: ResearchPlan,
        evidence: list[Evidence],
    ) -> ResearchReport:
        # ReportWriter 可被多个任务复用；每次调用先清空上次的用量。
        self.last_usage = Usage()
        # 把 Evidence 实例列表整理成一个字符串目录，作为 user_prompt 的一部分交给 LLM。
        evidence_catalog = "\n".join(
            (
                f"[{item.source_id}] title={item.title}; "
                f"url={item.url}; content={item.content}"
            )
            for item in evidence
        )
        # output_type 传入 ReportDraft 类：真实 LLM 会用它解析 JSON；FakeLLM 会检查预设实例类型。
        result = self.llm.generate_structured(
            system_prompt=(
                "Write a concise Markdown research report using only the supplied "
                "evidence. Cite factual claims with source IDs such as [S1]. "
                "Return JSON only."
            ),
            user_prompt=(
                f"Research topic: {topic}\n"
                f"Research plan: {plan.model_dump_json()}\n"
                f"Known evidence:\n{evidence_catalog or '(none)'}"
            ),
            output_type=ReportDraft,
        )
        self.last_usage = result.usage
        # result 是 LLMResult 外壳；value 才是本次要求生成的 ReportDraft 实例。
        draft = result.value

        # 1. 从真实 Evidence 列表提取允许使用的来源编号，例如 {"S1", "S2"}。
        known_source_ids = {item.source_id for item in evidence}
        # 2. findall 从报告正文找出所有 [S数字] 引用；去重时保留首次出现顺序。
        markdown_source_ids = list(
            dict.fromkeys(_CITATION_PATTERN.findall(draft.markdown))
        )
        # 3. 先保留模型声明顺序，再补入正文实际出现但模型漏报的编号。
        used_source_ids = list(
            dict.fromkeys([*draft.used_source_ids, *markdown_source_ids])
        )
        # 4. 临时转成集合做减法，得到“报告使用了、但 Evidence 中不存在”的编号。
        unknown_source_ids = sorted(set(used_source_ids) - known_source_ids)
        if unknown_source_ids:
            raise InvalidCitationError(
                f"unknown source IDs: {', '.join(unknown_source_ids)}"
            )

        evidence_by_id = {item.source_id: item for item in evidence}
        reference_lines = [
            (
                f"- [{source_id}] "
                f"[{evidence_by_id[source_id].title}]({evidence_by_id[source_id].url})"
            )
            for source_id in used_source_ids
        ]
        markdown = draft.markdown.rstrip()
        if reference_lines:
            markdown += "\n\n## References\n\n" + "\n".join(reference_lines)

        return ResearchReport(
            title=draft.title,
            markdown=markdown,
            html=render_html(markdown),
            used_source_ids=used_source_ids,
        )
