from pydantic import Field
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
