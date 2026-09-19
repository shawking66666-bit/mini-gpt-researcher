# Mini GPT Researcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 两周内从零实现使用 DeepSeek 与 Tavily 的双阶段深度研究 Agent，生成来源可追溯的 Markdown/HTML 报告，并提供 FastAPI、Streamlit、SQLite 和可重复测试。

**Architecture:** 确定性 Python 编排器维护状态、调用预算和引用关系；LLM只负责计划、反思和写作。模型、搜索、存储通过小接口隔离，使真实服务和 Fake 实现可互换。

**Tech Stack:** Python 3.11+、Pydantic 2、OpenAI Python SDK、Tavily Python SDK、FastAPI、Uvicorn、Streamlit、SQLite `sqlite3`、Markdown、pytest、httpx、Docker。

**Spec:** `docs/2026-09-12-gpt-researcher-learning-and-module-design.md`

## Global Constraints

- 首轮4个问题；反思最多2个补充问题；最多2轮。
- 每个问题最多5条候选结果；任务最多12个有效来源。
- 第一版只接 DeepSeek `deepseek-v4-flash` 非思考模式与 Tavily，不做多模型或多搜索商路由。
- 引用编号由 Python 分配，LLM不得创造未知来源。
- 单元测试只用 `FakeLLM`、`FakeSearch`，不得访问真实 API。
- Key只从环境变量或本地 `.env` 读取；创建或修改 `.env` 前需用户授权。
- 每个任务遵循失败测试→最小实现→测试通过→本地提交。
- 暂不实现多 Agent、MCP、本地文件研究、登录、PDF/Word和云部署。

## File Structure

```text
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── .gitignore
├── .env.example
├── Dockerfile
├── src/mini_researcher/
│   ├── config.py          # 配置与固定上限
│   ├── models.py          # Pydantic领域模型
│   ├── llm.py             # DeepSeek/FakeLLM边界
│   ├── search.py          # Tavily/FakeSearch边界
│   ├── planner.py         # 首轮问题规划
│   ├── evidence.py        # URL去重、证据、引用编号
│   ├── reflector.py       # 信息缺口和补充问题
│   ├── report.py          # Markdown/HTML与引用校验
│   ├── orchestrator.py    # 两轮确定性工作流
│   ├── repository.py      # SQLite持久化
│   ├── service.py         # 应用入口
│   ├── api.py             # FastAPI
│   └── ui.py              # Streamlit
├── tests/                 # 与上述模块对应的离线测试
└── tests/fixtures/research_cases/  # 三个固定真实需求
```

---

### Task 1: Project Foundation and Domain Models

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`
- Create: `src/mini_researcher/__init__.py`, `config.py`, `models.py`
- Test: `tests/test_config.py`, `tests/test_models.py`

**Interfaces:**
- Produces: `Settings`, `TaskStatus`, `ResearchQuestion`, `ResearchPlan`, `SearchResult`, `Evidence`, `Usage`, `ResearchState`, `ResearchReport`.
- Consumes: none.

- [x] **Step 1: Write failing tests**

```python
def test_fixed_limits():
    settings = Settings(deepseek_api_key="x", tavily_api_key="y")
    assert settings.initial_questions == 4
    assert settings.max_follow_up_questions == 2
    assert settings.max_research_rounds == 2
    assert settings.max_results_per_question == 5
    assert settings.max_final_sources == 12

def test_plan_rejects_five_questions():
    questions = [ResearchQuestion(id=f"q{i}", text=f"question {i}") for i in range(5)]
    with pytest.raises(ValueError):
        ResearchPlan(topic="topic", questions=questions)
```

- [x] **Step 2: Verify failure**

Run: `python -m pytest tests/test_config.py tests/test_models.py -v`

Expected: FAIL with missing `mini_researcher` package.

- [x] **Step 3: Implement package, settings, and models**

```python
class ResearchQuestion(BaseModel):
    id: str
    text: str = Field(min_length=3)
    round_number: int = Field(default=1, ge=1, le=2)

class ResearchPlan(BaseModel):
    topic: str = Field(min_length=3)
    questions: list[ResearchQuestion] = Field(min_length=1, max_length=4)
```

Use environment aliases `DEEPSEEK_API_KEY`, `TAVILY_API_KEY`. `.env.example` contains blank values only. Ignore `.env`, `.venv/`, `*.db`, `reports/`, caches and secrets.

- [x] **Step 4: Verify pass**

Run: `python -m pytest tests/test_config.py tests/test_models.py -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add pyproject.toml .gitignore .env.example src tests/test_config.py tests/test_models.py
git commit -m "feat: define research domain models"
```

### Task 2: Testable LLM and Search Boundaries

**Files:**
- Create: `src/mini_researcher/llm.py`, `search.py`
- Create: `tests/fakes.py`
- Test: `tests/test_llm.py`, `tests/test_search.py`

**Interfaces:**
- Produces: `LLMClient.generate_structured(system_prompt, user_prompt, output_type) -> LLMResult[T]`.
- Produces: `SearchProvider.search(query, max_results) -> list[SearchResult]`.
- Implementations: `DeepSeekLLM`, `FakeLLM`, `TavilySearch`, `FakeSearch`.

- [x] **Step 1: Write failing fake tests**

```python
def test_fake_llm_returns_typed_response():
    llm = FakeLLM([sample_plan])
    result = llm.generate_structured("system", "user", ResearchPlan)
    assert result.value == sample_plan
    assert result.usage.requests == 1

def test_fake_search_respects_limit():
    search = FakeSearch({"agent": [result_a, result_b]})
    assert search.search("agent", max_results=1) == [result_a]
```

- [x] **Step 2: Verify failure**

Run: `python -m pytest tests/test_llm.py tests/test_search.py -v`

Expected: FAIL with missing clients.

- [x] **Step 3: Implement adapters**

Use `OpenAI(api_key=key, base_url="https://api.deepseek.com")`, model `deepseek-v4-flash`, non-thinking mode, JSON output, Pydantic validation, usage capture, and one validation retry. Map Tavily data only inside `TavilySearch`:

```python
SearchResult(
    title=item.get("title") or "Untitled source",
    url=item["url"],
    content=item.get("content") or "",
    score=item.get("score"),
)
```

Reject blank queries. Convert provider failures to `LLMError`/`SearchError` without secret values.

- [x] **Step 4: Verify offline pass**

Run: `python -m pytest tests/test_llm.py tests/test_search.py -v`

Expected: PASS without network.

- [x] **Step 5: Commit**

```powershell
git add src/mini_researcher/llm.py src/mini_researcher/search.py tests
git commit -m "feat: add testable AI service boundaries"
```

### Task 3: Research Planner and Evidence Manager

**Files:**
- Create: `src/mini_researcher/planner.py`, `evidence.py`
- Test: `tests/test_planner.py`, `tests/test_evidence.py`

**Interfaces:**
- Produces: `Planner.create_plan(topic: str) -> ResearchPlan` with exactly four unique questions.
- Produces: `EvidenceManager.add(question, results) -> list[Evidence]` and `.all()`.

- [x] **Step 1: Write failing tests**

```python
def test_planner_returns_four_unique_questions():
    plan = Planner(FakeLLM([sample_plan])).create_plan("AI agents")
    assert len(plan.questions) == 4
    assert len({q.text.casefold() for q in plan.questions}) == 4

def test_evidence_deduplicates_tracking_urls():
    manager = EvidenceManager(max_sources=12)
    added = manager.add(question, [
        SearchResult(title="A", url="https://e.test/a?utm_source=x", content="one"),
        SearchResult(title="A2", url="https://e.test/a", content="two"),
    ])
    assert len(added) == 1
    assert added[0].source_id == "S1"
    assert added[0].url == "https://e.test/a"
```

- [x] **Step 2: Verify failure**

Run: `python -m pytest tests/test_planner.py tests/test_evidence.py -v`

Expected: FAIL with undefined planner/evidence manager.

- [x] **Step 3: Implement planning and deterministic evidence rules**

Planning prompt requests four non-overlapping dimensions: context, alternatives/evidence, constraints/risks, evaluation/outcomes. Normalize whitespace and reject duplicate text. Evidence normalization removes fragments and `utm_*`, `fbclid`, `gclid`, accepts only HTTP(S), and assigns `S1..S12` in insertion order.

- [x] **Step 4: Verify pass**

Run: `python -m pytest tests/test_planner.py tests/test_evidence.py -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add src/mini_researcher/planner.py src/mini_researcher/evidence.py tests
git commit -m "feat: plan research and track evidence"
```

### Task 4: First Round, Reflection, and Bounded Second Round

**Files:**
- Create: `src/mini_researcher/reflector.py`, `orchestrator.py`
- Test: `tests/test_reflector.py`, `tests/test_orchestrator.py`

**Interfaces:**
- Produces: `Reflector.find_gaps(topic, plan, evidence) -> list[ResearchQuestion]` with zero to two round-2 questions.
- Produces: `ResearchOrchestrator.run(topic: str) -> ResearchState`.

- [ ] **Step 1: Write failing workflow tests**

```python
def test_partial_search_failure_does_not_abort_research(orchestrator):
    state = orchestrator.run("AI agents")
    assert len(state.errors) == 1
    assert len(state.evidence) >= 1
    assert state.round_number <= 2

def test_reflector_returns_at_most_two_questions():
    result = Reflector(FakeLLM([follow_up_plan])).find_gaps("topic", plan, evidence)
    assert len(result) <= 2
    assert all(q.round_number == 2 for q in result)
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_reflector.py tests/test_orchestrator.py -v`

Expected: FAIL with missing workflow.

- [ ] **Step 3: Implement deterministic loop**

Loop over four initial questions, record status and usage, catch `SearchError` per question, preserve partial success, ask reflector once, search at most two follow-ups, then force status `ready_for_report`. Never permit a third round or more than12 sources.

- [ ] **Step 4: Verify pass**

Run: `python -m pytest tests/test_reflector.py tests/test_orchestrator.py -v`

Expected: PASS with no real calls.

- [ ] **Step 5: Commit**

```powershell
git add src/mini_researcher/reflector.py src/mini_researcher/orchestrator.py tests
git commit -m "feat: orchestrate bounded deep research"
```

### Task 5: Citation-Safe Markdown and HTML Reports

**Files:**
- Create: `src/mini_researcher/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Produces: `ReportWriter.write(topic, plan, evidence) -> ResearchReport`.
- Produces: `render_html(markdown_text: str) -> str`.

- [ ] **Step 1: Write failing citation tests**

```python
def test_report_accepts_known_source():
    draft = ReportDraft(title="Report", markdown="Claim [S1]", used_source_ids=["S1"])
    report = ReportWriter(FakeLLM([draft])).write("topic", plan, [evidence_s1])
    assert report.used_source_ids == ["S1"]

def test_report_rejects_unknown_source():
    draft = ReportDraft(title="Report", markdown="Claim [S9]", used_source_ids=["S9"])
    with pytest.raises(InvalidCitationError, match="S9"):
        ReportWriter(FakeLLM([draft])).write("topic", plan, [evidence_s1])

def test_html_has_clickable_link():
    assert '<a href="https://e.test">E</a>' in render_html("[E](https://e.test)")
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_report.py -v`

Expected: FAIL with missing report module.

- [ ] **Step 3: Implement report and validation**

Give the LLM only the known source catalog. Validate `used_source_ids` and citations found by `r"\[(S\d+)\]"`; append the reference list deterministically from evidence. Convert validated Markdown to HTML with raw HTML disabled/escaped.

- [ ] **Step 4: Verify pass**

Run: `python -m pytest tests/test_report.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/mini_researcher/report.py tests/test_report.py
git commit -m "feat: generate citation-safe reports"
```

### Task 6: SQLite Repository and Application Service

**Files:**
- Create: `src/mini_researcher/repository.py`, `service.py`
- Test: `tests/test_repository.py`, `tests/test_service.py`

**Interfaces:**
- Produces: `ResearchRepository.initialize/save_state/save_report/get_task/list_tasks`.
- Produces: `ResearchService.create_research(topic: str) -> ResearchState`.

- [ ] **Step 1: Write failing persistence tests**

```python
def test_repository_round_trips_state(tmp_path):
    repo = ResearchRepository(tmp_path / "research.db")
    repo.initialize()
    repo.save_state(sample_state)
    loaded = repo.get_task(sample_state.task_id)
    assert loaded.topic == sample_state.topic
    assert loaded.evidence[0].source_id == "S1"

def test_service_saves_completed_report(service, repository):
    state = service.create_research("AI agent evaluation")
    saved = repository.get_task(state.task_id)
    assert saved.status == TaskStatus.COMPLETED
    assert saved.report is not None
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_repository.py tests/test_service.py -v`

Expected: FAIL with missing repository/service.

- [ ] **Step 3: Implement SQLite and service**

Use `research_tasks`, `evidence`, `reports`; enable foreign keys, parameterized SQL and transactions; serialize nested non-query fields as JSON. Service validates topic, creates ID, saves status transitions, runs orchestrator and report writer, then saves success or explicit failure.

- [ ] **Step 4: Verify pass**

Run: `python -m pytest tests/test_repository.py tests/test_service.py -v`

Expected: PASS using temporary databases.

- [ ] **Step 5: Commit**

```powershell
git add src/mini_researcher/repository.py src/mini_researcher/service.py tests
git commit -m "feat: persist research task lifecycle"
```

### Task 7: FastAPI and Streamlit Delivery

**Files:**
- Create: `src/mini_researcher/api.py`, `ui.py`
- Test: `tests/test_api.py`, `tests/test_ui_smoke.py`

**Interfaces:**
- Produces routes: `POST /research`, `GET /research/{task_id}`, `GET /research/{task_id}/report`, `GET /research`.
- Produces a non-chat Streamlit task page using those endpoints.

- [ ] **Step 1: Write failing endpoint/UI tests**

```python
def test_blank_topic_returns_422(client):
    assert client.post("/research", json={"topic": "  "}).status_code == 422

def test_missing_task_returns_404(client):
    assert client.get("/research/missing").status_code == 404

def test_ui_has_task_controls():
    app = AppTest.from_file("src/mini_researcher/ui.py").run()
    assert app.text_area[0].label == "研究主题"
    assert app.button[0].label == "开始研究"
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_api.py tests/test_ui_smoke.py -v`

Expected: FAIL with missing API/UI.

- [ ] **Step 3: Implement API factory and task UI**

Keep v1 synchronous. Inject fakes in API tests. Map domain errors to stable codes without stack traces. UI sections are `研究计划`, `来源与证据`, `最终报告`, `本次用量`; use no chat bubbles; provide `.md` and `.html` downloads.

- [ ] **Step 4: Verify pass and manual launch**

Run: `python -m pytest tests/test_api.py tests/test_ui_smoke.py -v`

Expected: PASS.

Run: `python -m uvicorn mini_researcher.api:app --host 127.0.0.1 --port 8000`

Run separately: `python -m streamlit run src/mini_researcher/ui.py`

Expected after keys are separately authorized/configured: API docs and research task page load. Stop both manually.

- [ ] **Step 5: Commit**

```powershell
git add src/mini_researcher/api.py src/mini_researcher/ui.py tests
git commit -m "feat: deliver research API and UI"
```

### Task 8: Fixed Public Agent-Requirement Evaluations

**Files:**
- Create: `tests/fixtures/research_cases/enterprise_document_agent.md`
- Create: `tests/fixtures/research_cases/ecommerce_support_agent.md`
- Create: `tests/fixtures/research_cases/browser_automation_agent.md`
- Create: `docs/evaluation-rubric.md`, `docs/evaluation-results-v1.md`
- Test: `tests/test_evaluation_fixtures.py`

**Interfaces:**
- Produces three sanitized, stable public requirement fixtures and a 1–5 rubric.

- [ ] **Step 1: Write failing fixture test**

```python
@pytest.mark.parametrize("name", CASE_NAMES)
def test_fixture_has_traceable_metadata(name):
    text = (FIXTURE_DIR / name).read_text(encoding="utf-8")
    assert "source_url:" in text
    assert "captured_at:" in text
    assert "expected_research_points:" in text
    assert "private_contact:" not in text
```

- [ ] **Step 2: Verify missing fixtures**

Run: `python -m pytest tests/test_evaluation_fixtures.py -v`

Expected: FAIL because fixtures do not exist.

- [ ] **Step 3: Capture and sanitize cases**

Use publicly accessible requirements only. Preserve functional scope; record URL/date; remove names, contacts and private attachments. Rubric scores requirement coverage, question quality, source relevance/authority, citation completeness, risk identification, readability, stability and actual usage cost.

- [ ] **Step 4: Verify fixtures and run first evaluation**

Run: `python -m pytest tests/test_evaluation_fixtures.py -v`

Expected: PASS.

Run each fixture with identical limits. Record actual output scores and failures in `docs/evaluation-results-v1.md`; do not hand-edit generated reports to improve scores.

- [ ] **Step 5: Commit**

```powershell
git add tests/fixtures tests/test_evaluation_fixtures.py docs/evaluation-rubric.md docs/evaluation-results-v1.md
git commit -m "test: add fixed agent requirement evaluations"
```

### Task 9: Docker, README, and Final Verification

**Files:**
- Create: `Dockerfile`, `README.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Produces a reproducible local package, container, architecture guide and verified evidence.

- [ ] **Step 1: Verify package and offline suite**

Run: `python -m pip install -e ".[dev]"`

Expected: editable install succeeds in the project virtual environment.

Run: `python -m pytest -q`

Expected: all offline tests PASS.

- [ ] **Step 2: Add Dockerfile and exact README**

Use `python:3.11-slim`; run FastAPI on port8000 by default. README documents architecture, input→processing→output, offline tests, separately authorized key setup, API/UI commands, evaluation results, known limitations and attribution to GPT Researcher without claiming full parity.

- [ ] **Step 3: Build and inspect container**

Run: `docker build -t mini-gpt-researcher:local .`

Expected: build succeeds.

Run after `.env` authorization: `docker run --rm -p 8000:8000 --env-file .env mini-gpt-researcher:local`

Expected: Uvicorn listens on `0.0.0.0:8000`; logs contain no secret values. Stop manually.

- [ ] **Step 4: Final verification**

Run: `python -m pytest -q`

Run: `python -m compileall -q src tests`

Run: `git diff --check`

Run: `git status --short`

Expected: tests PASS, compilation and diff checks exit0, and `.env`, database and generated reports are not staged.

- [ ] **Step 5: Record actual evidence and commit**

Update `CLAUDE.md` with commands and actual results. Never claim Docker, real API or visual verification passed unless it ran in the current environment.

```powershell
git add Dockerfile README.md CLAUDE.md
git commit -m "docs: document verified local delivery"
```

## Two-Week Sequence

- Days1–2: Tasks1–2（类型、配置、DeepSeek/Tavily边界、Fake）。
- Days3–4: Task3（计划与证据）。
- Days5–6: Task4（第一轮、反思、第二轮）。
- Day7: 从输入到状态逐项复盘，修复后再继续。
- Days8–9: Task5（引用安全报告与HTML）。
- Day10: Task6（SQLite与服务）。
- Days11–12: Task7（FastAPI与Streamlit）。
- Day13: Task8（真实固定需求评估）。
- Day14: Task9（Docker、README、完整验证）。

## Learning Gate After Every Task

进入下一任务前，学习者必须能从真实代码与测试结果回答：

1. 这个模块接收的具体类型是什么？
2. 内部按什么顺序处理？
3. 返回的具体类型是什么？
4. 依赖失败时会发生什么？

答不清时先复盘当前任务，不继续叠加功能。
