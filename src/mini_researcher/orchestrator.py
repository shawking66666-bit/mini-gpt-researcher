from datetime import UTC, datetime
from uuid import uuid4

from mini_researcher.evidence import EvidenceManager
from mini_researcher.models import ResearchQuestion, ResearchState, TaskStatus, Usage
from mini_researcher.planner import Planner
from mini_researcher.reflector import Reflector
from mini_researcher.search import SearchError, SearchProvider


class ResearchOrchestrator:
    def __init__(
        self,
        planner: Planner,
        search: SearchProvider,
        reflector: Reflector,
        *,
        max_results_per_question: int,
        max_sources: int,
    ) -> None:
        self.planner = planner
        self.search = search
        self.reflector = reflector
        self.max_results_per_question = max_results_per_question
        self.max_sources = max_sources

    def run(self, topic: str) -> ResearchState:
        state = ResearchState(
            task_id=str(uuid4()),
            topic=topic,
            status=TaskStatus.PENDING,
            created_at=datetime.now(UTC),
        )

        state.status = TaskStatus.PLANNING
        state.plan = self.planner.create_plan(topic)
        self._accumulate_usage(state.usage, self.planner.last_usage)

        evidence_manager = EvidenceManager(max_sources=self.max_sources)
        state.status = TaskStatus.RESEARCHING
        state.round_number = 1
        self._search_questions(state.plan.questions, state, evidence_manager)

        state.status = TaskStatus.REFLECTING
        follow_up_questions = self.reflector.find_gaps(
            topic,
            state.plan,
            evidence_manager.all(),
        )
        self._accumulate_usage(state.usage, self.reflector.last_usage)

        if follow_up_questions:
            state.status = TaskStatus.RESEARCHING
            state.round_number = 2
            self._search_questions(follow_up_questions, state, evidence_manager)

        # Task 4只完成资料收集；REPORTING表示下一步应交给ReportWriter。
        state.evidence = evidence_manager.all()
        state.status = TaskStatus.REPORTING
        return state

    def _search_questions(
        self,
        questions: list[ResearchQuestion],
        state: ResearchState,
        evidence_manager: EvidenceManager,
    ) -> None:
        for question in questions:
            state.usage.search_requests += 1
            try:
                results = self.search.search(
                    question.text,
                    max_results=self.max_results_per_question,
                )
            except SearchError as error:
                # 单个问题失败只记录错误，不能丢弃其他问题已经获得的证据。
                state.errors.append(f"{question.id}: {error}")
                continue

            evidence_manager.add(question, results)

    @staticmethod
    def _accumulate_usage(total: Usage, addition: Usage) -> None:
        # Provider适配器返回本次调用用量；State保存整个研究任务的累计用量。
        total.llm_requests += addition.llm_requests
        total.search_requests += addition.search_requests
        total.input_tokens += addition.input_tokens
        total.output_tokens += addition.output_tokens
        total.tavily_credits += addition.tavily_credits
        total.estimated_cost_usd += addition.estimated_cost_usd
