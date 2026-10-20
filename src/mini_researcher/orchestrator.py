from datetime import UTC, datetime
from uuid import uuid4

from mini_researcher.evidence import EvidenceManager
from mini_researcher.models import RetrievalMode, ResearchQuestion, ResearchState, TaskStatus
from mini_researcher.planner import Planner
from mini_researcher.reflector import Reflector
from mini_researcher.retrieval import DocumentRetriever
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
        document_retriever: DocumentRetriever | None = None,
        rag_top_k: int = 3,
    ) -> None:
        self.planner = planner
        self.search = search
        self.reflector = reflector
        self.max_results_per_question = max_results_per_question
        self.max_sources = max_sources
        self.document_retriever = document_retriever
        self.rag_top_k = rag_top_k

    def run(self, topic: str, *, state: ResearchState | None = None) -> ResearchState:
        # Service 已创建任务时沿用同一实例和 task_id；单独调用时仍可自行创建状态。
        if state is None:
            state = ResearchState(
                task_id=str(uuid4()),
                topic=topic,
                status=TaskStatus.PENDING,
                created_at=datetime.now(UTC),
            )
        elif state.topic != topic:
            raise ValueError("state topic must match research topic")

        state.status = TaskStatus.PLANNING
        state.plan = self.planner.create_plan(topic)
        state.usage.accumulate(self.planner.last_usage)

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
        state.usage.accumulate(self.reflector.last_usage)

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
            web_results = []
            document_results = []
            if state.retrieval_mode in {RetrievalMode.WEB, RetrievalMode.HYBRID}:
                state.usage.search_requests += 1
                try:
                    web_results = self.search.search(
                        question.text, max_results=self.max_results_per_question,
                    )
                    state.usage.tavily_credits += self.search.credits_per_request
                except SearchError:
                    # 不保留供应商原始报错文字，另一个来源仍可继续提供证据。
                    state.errors.append(f"{question.id}: web search failed")
            if state.retrieval_mode in {RetrievalMode.DOCUMENT, RetrievalMode.HYBRID}:
                try:
                    if self.document_retriever is None or state.knowledge_base_id is None:
                        raise ValueError("document retriever or knowledge base is missing")
                    document_results = self.document_retriever.retrieve(
                        state.knowledge_base_id, question.text, self.rag_top_k,
                    )
                except Exception:
                    state.errors.append(f"{question.id}: document retrieval failed")
            # 两种来源交替进入同一个 EvidenceManager，共享去重与 12 条总上限。
            for index in range(max(len(web_results), len(document_results))):
                if index < len(web_results):
                    evidence_manager.add_search_results(question, [web_results[index]])
                if index < len(document_results):
                    evidence_manager.add_document_results(question, [document_results[index]])
