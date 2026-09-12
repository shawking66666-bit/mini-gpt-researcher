from mini_researcher.config import Settings


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

