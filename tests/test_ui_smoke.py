from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_ui_has_task_controls() -> None:
    ui_path = Path(__file__).parents[1] / "src" / "mini_researcher" / "ui.py"
    app = AppTest.from_file(ui_path).run()

    assert not app.exception
    assert app.text_area[0].label == "研究主题"
    assert app.button[0].label == "开始研究"


def test_ui_uses_portfolio_report_layout() -> None:
    ui_path = Path(__file__).parents[1] / "src" / "mini_researcher" / "ui.py"
    app = AppTest.from_file(ui_path).run()

    assert not app.exception
    assert [tab.label for tab in app.tabs] == [
        "最终报告",
        "研究计划",
        "证据来源",
        "运行详情",
    ]
    assert any("可验证的深度研究工作台" in item.value for item in app.caption)
