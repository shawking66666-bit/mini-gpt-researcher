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

三个容易混淆的入口职责不同：

```text
ResearchService.create_research(topic)：创建并完成一整个研究任务
ResearchOrchestrator.run(topic, state=state)：在同一个 State 上执行计划、搜索和反思
Planner.create_plan(topic)：只生成 ResearchPlan
```

一个 `ResearchState` 实例只对应一个 `task_id`。多个任务会有多个 State，并在 `research_tasks` 表中各占一行。同一任务运行期间多次调用 `save_state()`，保存的是这个任务在不同阶段的最新快照，不会创建多个同 ID 的任务。

## 哪些内容存在哪张表

| 表 | 保存内容 |
| --- | --- |
| `research_tasks` | 任务 ID、主题、状态、时间、轮次，以及计划、错误、用量的 JSON |
| `evidence` | 每条证据的编号、问题编号、标题、URL、内容 |
| `reports` | 报告标题、Markdown、HTML、引用编号 |

`task_id` 将三张表关联起来。`save_state()` 用 `?` 占位符传值，避免把用户主题拼成 SQL 代码；状态、证据、报告在同一个事务中提交，若其中一步失败会回滚。

`connection.executescript("""...""")` 中的三引号内容是传入的 SQL 字符串。Python 把它交给 SQLite，SQLite 再解释 `CREATE TABLE`；它不是 Python 注释。

## 内存 State 与 SQLite 快照

`state.evidence` 是当前 Python 进程内的列表；SQLite 是硬盘上的持久化数据库，程序退出后记录仍可保留。`save_state()` 中：

```sql
DELETE FROM evidence WHERE task_id = ?
```

只删除该任务在数据库里的旧 Evidence 快照，不会清空内存中的 `state.evidence`，也不会影响其他 `task_id`。随后 `executemany()` 把当前完整的 `state.evidence` 重新写入，避免列表已经变化而数据库仍残留旧记录。

同一个任务的第一轮问题和补充问题共用同一个 `EvidenceManager`，编号会从 `S1` 继续累加。当前项目按 `max_sources=12` 使用，因此最多保留 `S1` 到 `S12`；新任务会创建新的 Manager，再从 `S1` 开始。重复 URL 和超过上限的搜索结果不会变成 Evidence。

任务主记录使用：

```sql
ON CONFLICT(task_id) DO UPDATE
```

第一次保存同一 `task_id` 时新增记录，之后用当前状态更新这一行。因此数据库保存 `PENDING → REPORTING → COMPLETED/FAILED` 中的最新检查点，不自动保存完整状态变化历史。

状态、Evidence 和报告放在同一个事务中保存：只有全部 SQL 都成功才提交；任一步失败就回滚这一组修改，从而避免出现任务已经是 `COMPLETED`、但报告还没有写入的半成品状态。

## `get_task()` 如何恢复 State

`save_state()` 是“拆开保存”，`get_task(task_id)` 是“读取后重新组装”：

```text
research_tasks：SELECT + fetchone()，读取一个任务主体
evidence：SELECT + fetchall()，读取这个任务的多条证据
reports：SELECT + fetchone()，读取最多一份报告
  → 还原 ResearchPlan、Evidence、Usage、ResearchReport
  → 返回完整 ResearchState
```

- `model_validate(dict_row)`：验证 Python 字典并创建 Pydantic 实例。
- `model_validate_json(json_text)`：解析 JSON 字符串、验证并创建 Pydantic 实例。
- `json.loads(json_text)`：把普通 JSON 字符串恢复成 Python 列表等对象。
- 找不到 `task_id` 时返回 `None`。

`get_task()` 恢复的是该任务最后一次成功保存的快照，不是重新执行 Agent，也不是恢复每个历史阶段。

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
