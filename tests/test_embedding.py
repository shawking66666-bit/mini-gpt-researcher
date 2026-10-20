import pytest

from mini_researcher.config import Settings
from mini_researcher.embedding import EmbeddingConfigurationError, create_dashscope_embeddings


def test_embedding_factory_passes_model_dimension_and_endpoint(monkeypatch) -> None:
    seen = {}

    def fake_constructor(**kwargs):
        seen.update(kwargs)
        return object()

    monkeypatch.setattr("mini_researcher.embedding.OpenAIEmbeddings", fake_constructor)
    settings = Settings(deepseek_api_key="test", tavily_api_key="test", dashscope_api_key="private-test")

    created = create_dashscope_embeddings(settings)

    assert created is not None
    assert seen["model"] == "qwen3.7-text-embedding-flash"
    assert seen["dimensions"] == 1024
    assert seen["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert seen["api_key"] == "private-test"


def test_embedding_factory_rejects_missing_key_without_leaking_values() -> None:
    settings = Settings(deepseek_api_key="test", tavily_api_key="test", dashscope_api_key=None)
    with pytest.raises(EmbeddingConfigurationError, match="DASHSCOPE_API_KEY"):
        create_dashscope_embeddings(settings)
