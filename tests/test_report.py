import pytest

from mini_researcher.models import Evidence, ResearchPlan, ResearchQuestion
from mini_researcher.report import (
    InvalidCitationError,
    ReportDraft,
    ReportWriter,
    render_html,
)
from tests.fakes import FakeLLM


def _plan() -> ResearchPlan:
    return ResearchPlan(
        topic="AI agents",
        questions=[
            ResearchQuestion(id=f"q{number}", text=f"question {number}")
            for number in range(1, 5)
        ],
    )


def _evidence_s1() -> Evidence:
    return Evidence(
        source_id="S1",
        question_id="q1",
        title="Evidence source",
        url="https://example.com/source-1",
        content="verified evidence",
    )


def test_report_accepts_known_source_and_appends_reference() -> None:
    draft = ReportDraft(
        title="Report",
        markdown="Claim [S1]",
        used_source_ids=["S1"],
    )

    report = ReportWriter(FakeLLM([draft])).write(
        "AI agents",
        _plan(),
        [_evidence_s1()],
    )

    assert report.used_source_ids == ["S1"]
    assert "Claim [S1]" in report.markdown
    assert "[S1] [Evidence source](https://example.com/source-1)" in report.markdown
    assert report.html is not None


def test_report_rejects_unknown_declared_source() -> None:
    draft = ReportDraft(
        title="Report",
        markdown="Claim [S9]",
        used_source_ids=["S9"],
    )

    with pytest.raises(InvalidCitationError, match="S9"):
        ReportWriter(FakeLLM([draft])).write(
            "AI agents",
            _plan(),
            [_evidence_s1()],
        )


def test_report_rejects_unknown_source_hidden_in_markdown() -> None:
    draft = ReportDraft(
        title="Report",
        markdown="Known claim [S1]. Fabricated claim [S9].",
        used_source_ids=["S1"],
    )

    with pytest.raises(InvalidCitationError, match="S9"):
        ReportWriter(FakeLLM([draft])).write(
            "AI agents",
            _plan(),
            [_evidence_s1()],
        )


def test_report_includes_known_source_found_only_in_markdown() -> None:
    draft = ReportDraft(
        title="Report",
        markdown="Claim [S1]",
        # 模拟模型正文引用了 S1，却忘记在结构化字段中声明。
        used_source_ids=[],
    )

    report = ReportWriter(FakeLLM([draft])).write(
        "AI agents",
        _plan(),
        [_evidence_s1()],
    )

    assert report.used_source_ids == ["S1"]
    assert "[S1] [Evidence source](https://example.com/source-1)" in report.markdown


def test_render_html_has_clickable_link_and_escapes_raw_html() -> None:
    html = render_html("[E](https://e.test)\n\n<script>alert('x')</script>")

    assert '<a href="https://e.test">E</a>' in html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
