# Task 6：Service 与 SQLite 学习笔记

日期：2026-10-02。此笔记帮助复盘调用链，不要求背诵 SQL。

## 从哪里开始看

1. `src/mini_researcher/service.py`：`ResearchService.create_research(topic)` 是应用层入口。
2. `src/mini_researcher/orchestrator.py`：`run(topic, state=state)` 在同一个 `ResearchState` 上完成规划、搜索和反思。
3. `src/mini_researcher/report.py`：`write(topic, plan, evidence)` 返回经过引用检查的 `ResearchReport`。
4. `src/mini_researcher/repository.py`：保存和读取任务、证据及报告。
5. `tests/test_service.py`、`tests/test_repository.py`：用 FakeLLM、FakeSearch 和临时 SQLite 验证行为。

## 一次调用经过什么

```text
topic: str
  → Service 去掉首尾空白并检查主题
  → 创建 PENDING 的 ResearchState，保存到 SQLite
  → Orchestrator 修改同一个 ResearchState，返回 REPORTING
  → 保存计划、Evidence、错误和前两次 LLM 用量
  → ReportWriter 生成 ResearchReport，累计报告阶段用量
  → state.report = ResearchReport；state.status = COMPLETED
  → Repository 在一次事务中保存状态、证据和报告
  → Service 返回 ResearchState
```

`ResearchService` 管理一次业务从创建到保存；`ResearchOrchestrator` 管理研究内部的计划、搜索和反思。以后 FastAPI 接到用户主题，只需调用 Service。

## 哪些内容存在哪张表

| 表 | 保存内容 |
| --- | --- |
| `research_tasks` | 任务 ID、主题、状态、时间、轮次，以及计划、错误、用量的 JSON |
| `evidence` | 每条证据的编号、问题编号、标题、URL、内容 |
| `reports` | 报告标题、Markdown、HTML、引用编号 |

`task_id` 将三张表关联起来。`save_state()` 用 `?` 占位符传值，避免把用户主题拼成 SQL 代码；状态、证据、报告在同一个事务中提交，若其中一步失败会回滚。

`connection.executescript("""...""")` 中的三引号内容是传入的 SQL 字符串。Python 把它交给 SQLite，SQLite 再解释 `CREATE TABLE`；它不是 Python 注释。

## 失败时发生什么

- 空白主题：Service 抛出 `ValueError`，不创建任务。
- Planner 或报告生成失败：Service 将同一个任务标为 `FAILED`，记录错误类型并保存，返回可查询的 `ResearchState`。
- 报告引用不存在的来源：`ReportWriter` 抛出 `InvalidCitationError`，Service 保存失败状态；已经发生的 LLM 调用仍计入用量。
- 没有搜索证据：流程仍可返回没有引用的报告，不能伪造来源。
- 数据库写入失败：SQLite 回滚当前事务；数据库不可用时，异常仍会传给调用方。

当前保存的检查点是 `PENDING`、`REPORTING`、`COMPLETED` 或 `FAILED`。`PLANNING`、`RESEARCHING`、`REFLECTING` 是运行中的内存状态，当前同步版没有逐阶段写入数据库。

## 三个对象的角色

```text
ResearchState：一次任务的整体状态
ResearchReport：通过引用校验后的报告
Usage：各模块用量的累计值
```

理解到能从 `create_research(topic)` 追到数据库里的最终 `ResearchState`，并能指出失败时在哪一层处理，就足够进入 Task 7。
