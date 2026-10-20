from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from mini_researcher.config import Settings


class EmbeddingConfigurationError(ValueError):
    """私有文档检索所需的 Embedding 配置缺失。"""


def create_dashscope_embeddings(settings: Settings) -> Embeddings:
    """仅在文档路径被调用时，创建兼容 OpenAI 协议的千问 Embedding 客户端。"""

    if not settings.dashscope_api_key or not settings.dashscope_api_key.strip():
        raise EmbeddingConfigurationError("DASHSCOPE_API_KEY is required for document retrieval")
    return OpenAIEmbeddings(
        model=settings.dashscope_embedding_model,
        dimensions=settings.dashscope_embedding_dimension,
        base_url=settings.dashscope_base_url,
        api_key=settings.dashscope_api_key,
        check_embedding_ctx_length=False,
    )
