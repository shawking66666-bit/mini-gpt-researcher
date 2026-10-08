import os
from typing import Any
from urllib.parse import urlparse

import httpx
import streamlit as st


API_BASE_URL = os.getenv("MINI_RESEARCHER_API_URL", "http://127.0.0.1:8000")

STATUS_LABELS = {
    "pending": "等待开始",
    "planning": "正在规划",
    "researching": "正在检索",
    "reflecting": "正在反思",
    "reporting": "正在撰写",
    "completed": "研究完成",
    "failed": "研究失败",
}


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


def _source_domain(url: str) -> str:
    """将来源URL压缩成便于扫描的域名。"""

    return urlparse(url).netloc.removeprefix("www.") or "未知来源"


def _render_state(state: dict[str, Any] | None) -> None:
    """将一次研究结果组织成摘要、报告、计划、证据和运行详情。"""

    report_tab, plan_tab, evidence_tab, details_tab = st.tabs(
        ["最终报告", "研究计划", "证据来源", "运行详情"]
    )
    if state is None:
        with report_tab:
            st.info("在左侧输入研究主题，完成后报告会显示在这里。")
        with plan_tab:
            st.info("研究计划尚未生成。")
        with evidence_tab:
            st.info("尚未收集到来源与证据。")
        with details_tab:
            st.info("运行详情将在任务开始后显示。")
        return

    plan = state.get("plan") or {}
    evidence = state.get("evidence") or []
    report = state.get("report")
    usage = state.get("usage") or {}

    status = STATUS_LABELS.get(state.get("status", ""), state.get("status", "未知"))
    metric_columns = st.columns(4)
    metric_columns[0].metric("任务状态", status)
    metric_columns[1].metric("研究轮次", state.get("round_number", 0))
    metric_columns[2].metric("证据来源", len(evidence))
    metric_columns[3].metric("LLM 请求", usage.get("llm_requests", 0))

    with report_tab:
        if report:
            st.markdown(report["markdown"])
            download_columns = st.columns(2)
            download_columns[0].download_button(
                "下载 Markdown",
                data=report["markdown"],
                file_name=f"{state['task_id']}.md",
                mime="text/markdown",
                use_container_width=True,
            )
            if report.get("html"):
                download_columns[1].download_button(
                    "下载 HTML",
                    data=report["html"],
                    file_name=f"{state['task_id']}.html",
                    mime="text/html",
                    use_container_width=True,
                )
        else:
            st.info("报告尚未生成。")

    with plan_tab:
        questions = plan.get("questions") or []
        if questions:
            st.caption(f"围绕主题拆分为 {len(questions)} 个可检索问题")
            for question in questions:
                st.markdown(f"**{question['id']} · 第 {question['round_number']} 轮**")
                st.write(question["text"])
                st.divider()
        else:
            st.info("研究计划尚未生成。")

    with evidence_tab:
        if evidence:
            st.caption("来源按抓取顺序编号；展开可查看证据摘要与原始链接。")
            for item in evidence:
                label = f"{item['source_id']} · {_source_domain(item['url'])} · {item['title']}"
                with st.expander(label):
                    st.markdown(f"[打开原始来源]({item['url']})")
                    st.write(item["content"])
        else:
            st.info("尚未收集到可用证据。")

    with details_tab:
        st.markdown("#### 任务信息")
        st.code(state["task_id"], language=None)
        st.caption(f"创建时间：{state.get('created_at', '未知')}")
        st.markdown("#### 调用用量")
        usage_columns = st.columns(4)
        usage_columns[0].metric("搜索请求", usage.get("search_requests", 0))
        usage_columns[1].metric("输入 Token", usage.get("input_tokens", 0))
        usage_columns[2].metric("输出 Token", usage.get("output_tokens", 0))
        usage_columns[3].metric("Tavily Credits", usage.get("tavily_credits", 0))
        errors = state.get("errors") or []
        if errors:
            st.markdown("#### 错误记录")
            for error in errors:
                st.error(error)


st.set_page_config(
    page_title="Mini GPT Researcher",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(
    """
    <style>
    .block-container {max-width: 1180px; padding-top: 2.2rem; padding-bottom: 4rem;}
    [data-testid="stSidebar"] {border-right: 1px solid #dfe4ea;}
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #dfe4ea;
        border-radius: 12px;
        padding: 0.85rem 1rem;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
    }
    [data-testid="stExpander"] {border: 1px solid #e3e8ef; border-radius: 10px;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Mini GPT Researcher")
st.caption("可验证的深度研究工作台 · 规划、检索、反思与引用报告")

with st.sidebar:
    st.markdown("### 新建研究")
    st.caption("输入一个需要多来源检索和结构化分析的主题。")
    topic = st.text_area(
        "研究主题",
        placeholder="例如：AI Agent 应用岗位需要哪些能力？",
        height=180,
    )

    if st.button("开始研究", type="primary", use_container_width=True):
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

    st.divider()
    st.markdown("### 研究流程")
    st.caption("Plan → Search → Evidence → Reflect → Report")

state = st.session_state.get("research_state")
if state:
    st.markdown(f"### {state.get('topic', '研究结果')}")
    st.caption(f"任务 ID：{state['task_id']}")
else:
    st.markdown("### 研究结果")
    st.write("从左侧开始一个研究任务，结果会以报告、计划、证据和运行详情分区呈现。")

_render_state(state)
