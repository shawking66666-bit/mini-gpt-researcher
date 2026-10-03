from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_ui_has_task_controls() -> None:
    ui_path = Path(__file__).parents[1] / "src" / "mini_researcher" / "ui.py"
    app = AppTest.from_file(ui_path).run()

    assert not app.exception
    assert app.text_area[0].label == "研究主题"
    assert app.button[0].label == "开始研究"
