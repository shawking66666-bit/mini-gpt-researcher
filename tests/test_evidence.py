from mini_researcher.evidence import EvidenceManager
from mini_researcher.models import ResearchQuestion, SearchResult


def test_evidence_manager_deduplicates_tracking_urls() -> None:
    question = ResearchQuestion(id="q1", text="What is an AI agent?")
    results = [
        SearchResult(
            title="Source A",
            url="https://example.com/article?utm_source=newsletter",
            content="first version",
        ),
        SearchResult(
            title="Source A duplicate",
            url="https://example.com/article",
            content="duplicate version",
        ),
    ]
    manager = EvidenceManager(max_sources=12)

    added = manager.add(question, results)

    # 清理跟踪参数后，两条结果指向同一页面，因此只新增第一条证据。
    assert len(added) == 1
    assert added[0].source_id == "S1"
    assert added[0].question_id == "q1"
    assert added[0].url == "https://example.com/article"
    assert manager.all() == added


def test_evidence_manager_stops_at_source_limit() -> None:
    question = ResearchQuestion(id="q1", text="What is an AI agent?")
    results = [
        SearchResult(
            title=f"Source {number}",
            url=f"https://example.com/article-{number}",
            content=f"content {number}",
        )
        for number in range(1, 4)
    ]
    manager = EvidenceManager(max_sources=2)

    added = manager.add(question, results)

    assert [evidence.source_id for evidence in added] == ["S1", "S2"]
    assert manager.all() == added


def test_evidence_manager_removes_fragment_and_tracking_parameters() -> None:
    question = ResearchQuestion(id="q1", text="What is an AI agent?")
    manager = EvidenceManager(max_sources=12)

    added = manager.add(
        question,
        [
            SearchResult(
                title="Source A",
                url=(
                    "HTTPS://EXAMPLE.COM/article?"
                    "topic=agent&fbclid=abc&gclid=xyz&utm_medium=email#summary"
                ),
                content="useful content",
            )
        ],
    )

    assert added[0].url == "https://example.com/article?topic=agent"


def test_evidence_manager_deduplicates_across_multiple_add_calls() -> None:
    first_question = ResearchQuestion(id="q1", text="What is an AI agent?")
    second_question = ResearchQuestion(id="q2", text="How are agents evaluated?")
    manager = EvidenceManager(max_sources=12)

    first_added = manager.add(
        first_question,
        [
            SearchResult(
                title="Source A",
                url="https://example.com/a",
                content="first source",
            )
        ],
    )
    second_added = manager.add(
        second_question,
        [
            SearchResult(
                title="Source A duplicate",
                url="https://example.com/a#details",
                content="duplicate source",
            ),
            SearchResult(
                title="Source B",
                url="https://example.com/b",
                content="second source",
            ),
        ],
    )

    assert [evidence.source_id for evidence in first_added] == ["S1"]
    assert [evidence.source_id for evidence in second_added] == ["S2"]
    assert [evidence.question_id for evidence in manager.all()] == ["q1", "q2"]
