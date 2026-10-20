from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """External service credentials and bounded research limits."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    deepseek_api_key: str = Field(repr=False)
    tavily_api_key: str = Field(repr=False)
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_thinking_enabled: bool = False

    initial_questions: int = 4
    max_follow_up_questions: int = 2
    max_research_rounds: int = 2
    max_results_per_question: int = 5
    max_final_sources: int = 12

    # 联网研究不需要 Embedding；只有上传或检索私有文档时才检查这把密钥。
    dashscope_api_key: str | None = Field(default=None, repr=False)
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_embedding_model: str = "qwen3.7-text-embedding-flash"
    dashscope_embedding_dimension: int = Field(default=1024, gt=0)
    rag_top_k: int = Field(default=3, gt=0)
    rag_chunk_size: int = Field(default=800, gt=0)
    rag_chunk_overlap: int = Field(default=120, ge=0)

    @model_validator(mode="after")
    def validate_chunk_window(self) -> "Settings":
        if self.rag_chunk_overlap >= self.rag_chunk_size:
            raise ValueError("rag_chunk_overlap must be smaller than rag_chunk_size")
        return self
