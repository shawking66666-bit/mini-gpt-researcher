from mini_researcher.config import Settings
from pydantic import ValidationError
import pytest


def test_settings_use_fixed_research_limits() -> None:
    settings = Settings(deepseek_api_key="deepseek-test", tavily_api_key="tavily-test")

    assert settings.initial_questions == 4
    assert settings.max_follow_up_questions == 2
    assert settings.max_research_rounds == 2
    assert settings.max_results_per_question == 5
    assert settings.max_final_sources == 12


def test_settings_use_deepseek_v4_flash_without_thinking() -> None:
    settings = Settings(deepseek_api_key="deepseek-test", tavily_api_key="tavily-test")

    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.deepseek_model == "deepseek-v4-flash"
    assert settings.deepseek_thinking_enabled is False


def test_rag_defaults_do_not_require_embedding_key_for_web_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 本测试验证默认值，不应读取开发者本机的环境变量或 .env。
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    settings = Settings(
        deepseek_api_key="deepseek-test",
        tavily_api_key="tavily-test",
        _env_file=None,
    )

    assert not settings.dashscope_api_key
    assert settings.dashscope_embedding_model == "qwen3.7-text-embedding-flash"
    assert settings.dashscope_embedding_dimension == 1024
    assert settings.rag_top_k == 3
    assert settings.rag_chunk_size == 800
    assert settings.rag_chunk_overlap == 120


@pytest.mark.parametrize(
    "overrides",
    [
        {"dashscope_embedding_dimension": 0},
        {"rag_top_k": 0},
        {"rag_chunk_size": 0},
        {"rag_chunk_overlap": -1},
        {"rag_chunk_size": 100, "rag_chunk_overlap": 100},
    ],
)
def test_rag_rejects_invalid_limits(overrides: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        Settings(
            deepseek_api_key="deepseek-test",
            tavily_api_key="tavily-test",
            **overrides,
        )

