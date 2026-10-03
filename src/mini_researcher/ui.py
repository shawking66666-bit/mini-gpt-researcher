import os
from typing import Any

import httpx
import streamlit as st


API_BASE_URL = os.getenv("MINI_RESEARCHER_API_URL", "http://127.0.0.1:8000")


def _request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    """调用FastAPI并把网络错误转换为适合页面显示的错误。"""

    try:
        response = httpx.request(
            method,
            f"{API_BASE_URL}{path}",
            timeout=120.0,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise RuntimeError("无法完成研究请求，请检查API服务。") from error


def _render_state(state: dict[str, Any]) -> None:
    plan = state.get("plan") or {}
    evidence = state.get("evidence") or []
    report = state.get("report")
    usage = state.get("usage") or {}

    st.subheader("研究计划")
    questions = plan.get("questions") or []
    if questions:
        for question in questions:
            st.write(f"{question['id']}：{question['text']}")
    else:
        st.info("研究计划尚未生成。")

    st.subheader("来源与证据")
    if evidence:
        for item in evidence:
            st.markdown(f"**[{item['source_id']}] {item['title']}**")
            st.write(item["url"])
            st.write(item["content"])
    else:
        st.info("尚未收集到可用证据。")

    st.subheader("最终报告")
    if report:
        st.markdown(report["markdown"])
        st.download_button(
            "下载 Markdown",
            data=report["markdown"],
            file_name=f"{state['task_id']}.md",
            mime="text/markdown",
        )
        if report.get("html"):
            st.download_button(
                "下载 HTML",
                data=report["html"],
                file_name=f"{state['task_id']}.html",
                mime="text/html",
            )
    else:
        st.info("报告尚未生成。")

    st.subheader("本次用量")
    st.json(usage)


st.set_page_config(page_title="Mini GPT Researcher", layout="wide")
st.title("Mini GPT Researcher")
topic = st.text_area("研究主题", placeholder="例如：AI Agent 应用岗位需要哪些能力？")

if st.button("开始研究", type="primary"):
    if not topic.strip():
        st.warning("请输入研究主题。")
    else:
        with st.spinner("正在规划、搜索、反思并生成报告……"):
            try:
                st.session_state["research_state"] = _request(
                    "POST",
                    "/research",
                    json={"topic": topic},
                )
            except RuntimeError as error:
                st.error(str(error))

state = st.session_state.get("research_state")
if state:
    st.caption(f"任务ID：{state['task_id']}｜状态：{state['status']}")
    _render_state(state)
