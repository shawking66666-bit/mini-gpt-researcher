from pathlib import Path

import pytest


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "research_cases"
CASE_NAMES = [
    "enterprise_document_agent.md",
    "ecommerce_support_agent.md",
    "browser_automation_agent.md",
]


@pytest.mark.parametrize("name", CASE_NAMES)
def test_fixture_has_traceable_sanitized_metadata(name: str) -> None:
    """固定案例必须可追溯且不携带私人联系方式，否则评估无法公开复现。"""

    text = (FIXTURE_DIR / name).read_text(encoding="utf-8")

    assert "source_url:" in text
    assert "captured_at:" in text
    assert "expected_research_points:" in text
    assert "private_contact:" not in text
    assert "## Sanitized requirement" in text
