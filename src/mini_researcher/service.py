from datetime import UTC, datetime
from uuid import uuid4

from mini_researcher.models import ResearchState, TaskStatus
from mini_researcher.orchestrator import ResearchOrchestrator
from mini_researcher.report import ReportWriter
from mini_researcher.repository import ResearchRepository


class ResearchService:
    """应用入口：创建任务，调用研究与报告模块，保存最终结果。"""

    def __init__(
        self,
        orchestrator: ResearchOrchestrator,
        report_writer: ReportWriter,
        repository: ResearchRepository,
    ) -> None:
        self.orchestrator = orchestrator
        self.report_writer = report_writer
        self.repository = repository

    def create_research(self, topic: str) -> ResearchState:
        """以同一个 task_id 完成研究；业务失败时返回持久化的 FAILED 状态。"""

        normalized_topic = topic.strip()
        if not normalized_topic:
            raise ValueError("topic must not be blank")

        state = ResearchState(
            task_id=str(uuid4()),
            topic=normalized_topic,
            status=TaskStatus.PENDING,
            created_at=datetime.now(UTC),
        )
        # 第一次写库，让后续失败也能通过 task_id 找到这个任务。
        self.repository.save_state(state)

        try:
            # Orchestrator 修改传入的同一个 ResearchState，生成计划与证据。
            state = self.orchestrator.run(normalized_topic, state=state)
            self.repository.save_state(state)

            if state.plan is None:
                raise ValueError("research plan is missing")
            try:
                state.report = self.report_writer.write(
                    state.topic,
                    state.plan,
                    state.evidence,
                )
            finally:
                # 模型已返回但引用校验失败时，也要记录这次真实发生的 LLM 用量。
                state.usage.accumulate(self.report_writer.last_usage)
            state.status = TaskStatus.COMPLETED
            # save_state 在同一 SQLite 事务中保存状态与 state.report。
            self.repository.save_state(state)
        except Exception as error:
            # 保存错误类型以供定位；不将可能含密钥或私密内容的异常原文写入数据库。
            state.status = TaskStatus.FAILED
            state.report = None
            state.errors.append(f"research failed: {type(error).__name__}")
            self.repository.save_state(state)

        return state
