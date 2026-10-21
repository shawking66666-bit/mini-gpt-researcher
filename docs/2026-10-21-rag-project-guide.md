# Mini GPT Researcher：中文项目导读与学习路线

## 一句话说清楚

这是一个本地运行的深度研究 Agent：输入主题后，它先规划问题，再从网页、已上传的 PDF/Markdown，或两者同时收集资料；把资料整理为有编号的证据，必要时补搜，最后生成带来源的报告。它参考 GPT Researcher 的公开产品思路，但不是原项目的完整复刻。

RAG 是新增的“私有文档检索”能力，不是给模型重新训练：文档被切成片段、转换为向量并存入 Chroma；研究问题也转换为向量，检索到的相关片段再进入原有 Evidence → 报告流程。项目当前支持 `web`、`document`、`hybrid` 三种模式。

## 展示时怎么说

**作品集短描述：** 独立实现一个支持网页搜索与私有文档混合检索的研究 Agent。系统以 DeepSeek 生成研究计划、反思证据缺口和撰写报告；以 Tavily 检索网页，以千问 Embedding、LangChain 文档加载/切分和 Chroma 检索 PDF/Markdown。统一 Evidence 模型负责去重、编号与来源类型记录，确定性代码负责两轮研究上限、引用编号校验、状态与 SQLite 持久化，并通过 FastAPI 和 Streamlit 提供接口与演示页面。

**面试时的 30 秒说法：** “我没有只做一个聊天界面，而是把研究拆成计划、检索、证据整理、缺口反思和报告几个步骤。后来我在网页检索之外加了 RAG：上传文档后先切分并建向量索引，提问时找相关片段，把网页和文档片段统一成可追溯的 Evidence。模型负责需要理解和写作的部分，代码负责流程边界和引用检查。我用离线测试验证模块，并做过一次真实混合研究冒烟测试。”

**边界要说准：** 已有本地自动化测试和一次受控真实混合运行；这不代表生产级稳定性。引用编号存在性检查不等于“报告结论已被原文语义支持”。当前也没有多用户权限、OCR 或异步任务队列；加入 RAG 后的 Docker 镜像尚未重新验收。不要把它描述成完整复刻、企业线上交付或事实核查系统。

## 先分清两条链

| 链 | 用户做什么 | 代码主线 | 产物 |
| --- | --- | --- | --- |
| 文档入库 | 上传 PDF/Markdown | `api.py:create_knowledge_base` → `knowledge.py:KnowledgeBaseService.create` → Loader/切分 → 千问 Embedding → Chroma | `knowledge_base_id`、本地索引与就绪清单 |
| 发起研究 | 输入主题并选模式 | `api.py:create_research` → `service.py:ResearchService.create_research` → `orchestrator.py:run` → `report.py:ReportWriter.write` → `repository.py:save_state` | `ResearchState`、Evidence、Markdown/HTML 报告 |

上传文档**不会自动开始研究**；`knowledge_base_id` 是把已经建好的索引交给后续 `document` 或 `hybrid` 请求使用。`web` 模式不需要文档索引。

研究链内部再拆开看：

```text
ResearchCreateRequest(topic, retrieval_mode, knowledge_base_id)
  → ResearchService 创建 task_id 和 PENDING 状态，先存 SQLite
  → Orchestrator 调 Planner，得到 ResearchPlan（含 ResearchQuestion 列表）
  → 对每个问题按模式调用 Tavily / Chroma，得到 SearchResult / DocumentResult
  → EvidenceManager 去重、统一编号，最多保留 12 条 Evidence
  → Reflector 判断缺口；有补充问题才执行第二轮检索
  → ReportWriter 把 Evidence 交给 LLM 写 ReportDraft，检查引用编号
  → ResearchService 保存完成或失败状态；Repository 存最新快照与报告
```

`Reflector` 只提出是否需要补充的问题，真正执行第二轮的是 `Orchestrator`。`ResearchState` 是一个任务的运行状态和结果容器，不是模型的长期记忆；模型仅在 Planner、Reflector、ReportWriter 的调用中看到相应提示词和被传入的资料。

## 怎么读代码：用一次请求带着看

先不要逐行背文件。用一个最小例子：“上传一份非敏感 Markdown，选择 `hybrid`，主题填‘这份文档中的方案与公开资料有哪些异同？’”。启动方式与接口示例见 [README](../README.md#本地运行)，不要把真实密钥、上传文档或本地索引提交到 Git。

1. **看输入从哪来。** `src/mini_researcher/ui.py` 的 `_request` 将页面操作变成 HTTP 请求；`api.py` 中的 `ResearchCreateRequest` 检查主题、模式和知识库 ID，`create_research` 路由把请求交给 Service。先分清“请求体对象”和“研究状态对象”不是同一个类。
2. **看入库独立发生。** `api.py:create_knowledge_base` 接收上传文件；`knowledge.py:KnowledgeBaseService.create` 做文件校验、加载、切分、向量入库，返回 `knowledge_base_id`。这里重点追踪：原始字节 → 文本页 → chunk → 向量索引。
3. **看任务如何创建。** `service.py:ResearchService.create_research` 创建一个 `ResearchState` 与 `task_id`，保存初始快照，再调用 `orchestrator.run`。`task_id` 标识一次研究，不等于计划里研究问题的数量。
4. **看两种检索如何合流。** `orchestrator.py:_search_questions` 根据 `retrieval_mode` 调 `search.py:TavilySearch.search` 和/或 `retrieval.py:ChromaDocumentRetriever.retrieve`；返回的 `SearchResult` / `DocumentResult` 交给 `evidence.py:EvidenceManager`，变成同一种 `Evidence`。这是 RAG 接入原 Agent 的关键接缝。
5. **看反思与报告。** `orchestrator.py:run` 调 `reflector.py:find_gaps`，只有返回补充问题时才二次检索。然后 `report.py:ReportWriter.write` 要求 LLM 返回 `ReportDraft`，代码检查正文和结构化字段里的引用编号是否属于真实 Evidence，生成 `ResearchReport`。这只检查编号，不检查证据是否真正支持结论。
6. **看状态如何落盘。** 回到 `service.py`，观察成功和失败两条路径；再看 `repository.py:save_state`、`get_task`。SQLite 保留每个任务的最新快照；并非每次保存都会多出一条新的任务。

每看一步，只回答四个问题：**输入是什么类型、谁调用它、输出是什么类型、失败会怎样**。建议先跑离线测试，给上述路径各找一条对应测试；能不用看提示独立讲通 `DocumentResult → Evidence → ResearchReport`，再考虑增加新功能。

## 下一步学习和改进

先做一次可复述的演示：上传公开、非敏感文档，执行 `document` 和 `hybrid` 各一次，手动检查报告中至少一条结论是否真的被对应来源支持，并记下检索遗漏或误引。再按实际问题选下一步：若证据不支持结论，优先做逐条主张—证据校验；若文档找不准，先评估切分与检索结果；若响应太慢，再考虑异步任务。不要把“加更多框架”当作默认升级方向。
