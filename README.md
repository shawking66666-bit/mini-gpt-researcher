# Mini GPT Researcher

一个面向学习与作品集展示的深度研究 Agent。用户输入研究主题后，系统会规划问题、联网搜索、整理证据、判断信息缺口，并生成带来源编号的 Markdown 与 HTML 报告。

本项目参考 [GPT Researcher](https://github.com/assafelovic/gpt-researcher) 的公开产品思路，从零重写了一个范围更小、便于解释和测试的版本。它不是 GPT Researcher 的完整复刻，也不声称具备生产级可靠性。

## 它解决什么问题

普通聊天模型可以直接回答问题，但答案可能没有经过搜索，也不容易追溯来源。本项目把一次研究拆成可检查的流水线：

```text
研究主题
  -> Planner：生成结构化研究计划
  -> TavilySearch：逐个问题搜索公开网页
  -> EvidenceManager：去重并编号为 S1、S2……
  -> Reflector：判断证据是否充足，必要时生成补充问题
  -> ReportWriter：生成报告并校验引用编号
  -> ResearchRepository：把任务、证据和报告保存到 SQLite
  -> FastAPI / Streamlit：提供接口和演示页面
```

LLM 负责规划、反思和写作；Python 代码负责流程顺序、搜索上限、状态、引用校验、失败处理和持久化。

## 当前能力

- DeepSeek 结构化输出：研究计划、证据反思、最终报告
- Tavily 联网搜索，并用统一 `SearchResult` 格式隔离外部 SDK
- 最多两轮研究：首轮搜索 + 必要时的补充搜索
- Evidence 去重、连续编号、最多保留 12 条
- 报告引用只允许使用真实 Evidence 编号
- SQLite 保存任务的最新状态、证据和报告
- FastAPI：创建、列表、查询任务和读取报告
- Streamlit：输入主题、查看计划/证据/报告/用量、下载 Markdown/HTML
- FakeLLM 与 FakeSearch 离线测试，不消耗真实 API

## 项目结构

```text
src/mini_researcher/
  api.py           # FastAPI 入口与真实依赖组装
  service.py       # 单次研究任务的应用服务
  orchestrator.py  # plan -> search -> reflect -> search 的流程调度
  planner.py       # 生成 ResearchPlan
  search.py        # Tavily/Fake 搜索边界
  evidence.py      # 搜索结果去重、编号与容量限制
  reflector.py     # 判断证据缺口并产生补充问题
  report.py        # 报告生成、引用校验与 HTML 转换
  repository.py    # SQLite 持久化
  ui.py            # Streamlit 页面
tests/             # 离线单元、集成、API 与 UI 冒烟测试
docs/              # 设计、学习笔记和固定案例评估
```

## 本地运行

要求 Python 3.11+。以下命令在 PowerShell 中执行。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

复制 `.env.example` 为本地 `.env`，只在本机填写密钥，不要提交 `.env`：

```dotenv
DEEPSEEK_API_KEY=你的密钥
TAVILY_API_KEY=你的密钥
```

启动 API：

```powershell
.venv\Scripts\python.exe -m uvicorn mini_researcher.api:app --reload
```

浏览器打开 `http://127.0.0.1:8000/docs` 查看接口文档。主要接口：

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| POST | `/research` | 执行一次研究并返回完整状态 |
| GET | `/research` | 列出已保存任务 |
| GET | `/research/{task_id}` | 查询一个任务 |
| GET | `/research/{task_id}/report` | 获取最终报告 |

启动 UI（API 需保持运行）：

```powershell
.venv\Scripts\python.exe -m streamlit run src/mini_researcher/ui.py
```

## Docker

```powershell
docker build -t mini-gpt-researcher:local .
docker run --rm -p 8000:8000 --env-file .env mini-gpt-researcher:local
```

容器默认运行 FastAPI 的 `8000` 端口，并以非 root 用户运行。2026-10-07 已在 Docker Desktop 4.84.0 / Engine 29.6.2 上完成本地验证：镜像构建成功，容器内用户为 `researcher`（UID 10001），`/openapi.json` 与 `/research` 均返回 HTTP 200。真实研究仍需通过 `.env` 单独提供 DeepSeek 与 Tavily 密钥。

## 测试与评估

离线测试：

```powershell
.venv\Scripts\python.exe -m pytest -q
```

2026-10-07 的本地结果为 `62 passed`。这些测试证明确定性流程、数据模型、错误路径、持久化、API 和 UI 冒烟行为可重复，不证明真实搜索质量或模型回答正确。

固定评估案例位于 `tests/fixtures/research_cases/`，评分规则见 `docs/evaluation-rubric.md`，当前真实结果见 `docs/evaluation-results-v1.md`。真实 DeepSeek/Tavily 评测尚未运行，因此没有填写虚构分数。

## 已知限制

- `POST /research` 是同步请求，长任务可能超时；没有后台任务队列。
- 没有用户登录、权限隔离、限流和生产级审计。
- 搜索质量依赖 Tavily，结论仍需人工复核原始来源。
- 引用校验能阻止未知编号，但不能自动证明引用内容支持对应结论。
- SQLite 只保存任务最新快照，不保存完整状态变化历史。
- 当前没有 RAG 私有知识库、浏览器自动化或多 Agent 协作。
- 真实 API 固定案例评测仍待验证；Docker 只完成无密钥的启动与查询接口验证。

## 作品集表述边界

可以描述为：独立实现了一个可测试、可持久化、带 API 和演示页面的深度研究 Agent 闭环，并能解释模型、搜索、证据、反思、报告和状态之间的边界。

不应描述为：完整复刻 GPT Researcher、已达到生产级、实现通用自主 Agent、实现企业 RAG，或真实评测已经通过。
