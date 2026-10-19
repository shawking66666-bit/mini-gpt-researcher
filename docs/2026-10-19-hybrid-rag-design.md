# Mini GPT Researcher 混合 RAG 设计

## 1. 目标

在现有 Mini GPT Researcher 的联网研究闭环上，增加私有 PDF、Markdown 文档检索能力。研究任务可以选择仅联网、仅私有文档或混合检索，并将两种来源统一转换为可反思、可引用、可持久化的 `Evidence`。

第一版用于作品集展示和 LangChain/RAG 学习，不建设完整的企业知识库平台。

## 2. 设计原则

- 保留现有 `ResearchService`、`ResearchOrchestrator`、`Planner`、`Reflector`、`ReportWriter` 主链路。
- LangChain只负责文档加载、文本切分、Embedding接口、Chroma集成与Retriever，不重写整个Agent。
- Tavily和私有文档是两个并列检索来源，最终进入同一个 `EvidenceManager`。
- 自动化测试使用Fake组件，不访问真实Embedding、LLM或搜索API。
- 用户上传文件、向量索引和密钥均不得提交Git。
- 数据库迁移必须保留已有网页任务，不删除旧数据重建。

## 3. 范围

### 3.1 第一版包含

- 上传PDF与Markdown文件。
- 使用LangChain Loader读取文档。
- 使用 `RecursiveCharacterTextSplitter` 切分中英文文本。
- 使用阿里云百炼千问Embedding API生成向量。
- 使用本地Chroma持久化向量索引。
- 支持 `web`、`document`、`hybrid` 三种检索模式。
- 网页与文档结果统一转换为 `Evidence`。
- 文档来源展示文件名和可用页码。
- 保留最多两轮研究、最多12条最终Evidence和引用编号校验。
- 为迁移、入库、检索、降级、报告和UI提供自动化测试。

### 3.2 第一版不包含

- Word、Excel、图片OCR和扫描版PDF。
- 多用户、登录、权限和企业级文档隔离。
- 云向量数据库、任务队列和分布式部署。
- 长期对话记忆、LangGraph重写和多Agent。
- 客服意图识别、转人工等垂直业务功能。
- 本地FastEmbed实现；它只作为未来可插拔的离线Embedding方案。

## 4. 总体架构

```text
Streamlit
  ├─ 上传 PDF / Markdown
  └─ 输入研究主题与检索模式
          ↓
FastAPI
  ├─ KnowledgeBaseService
  │   └─ Loader → Splitter → DashScopeEmbedding → Chroma
  │
  └─ ResearchService
      └─ ResearchOrchestrator
          ├─ Planner
          ├─ TavilySearch
          ├─ ChromaDocumentRetriever
          ├─ EvidenceManager
          └─ Reflector
                  ↓
            ReportWriter
                  ↓
       SQLite + Chroma + Streamlit
```

旧的纯网络请求保持兼容。没有 `knowledge_base_id` 时默认使用 `web` 模式。

## 5. 数据模型

### 5.1 Evidence

`Evidence` 扩展为同时表达网页与本地文档：

```python
class Evidence(BaseModel):
    source_id: str
    question_id: str
    source_type: Literal["web", "document"]
    title: str
    content: str
    url: str | None = None
    document_name: str | None = None
    page_number: int | None = None
    chunk_index: int | None = None
```

条件约束：

- `web` 必须提供合法的HTTP/HTTPS URL。
- `document` 必须提供 `document_name`，URL可以为空。
- PDF尽量保留页码；Markdown页码为空。

### 5.2 DocumentResult

LangChain的 `Document` 不直接泄漏到业务层，先适配为：

```python
class DocumentResult(BaseModel):
    document_name: str
    content: str
    page_number: int | None = None
    chunk_index: int
    score: float | None = None
```

### 5.3 检索模式

```python
class RetrievalMode(StrEnum):
    WEB = "web"
    DOCUMENT = "document"
    HYBRID = "hybrid"
```

`ResearchState`增加 `retrieval_mode` 与可选的 `knowledge_base_id`；SQLite的
`research_tasks` 表同步保存这两个字段，使历史任务可以复现其来源配置。

## 6. 组件边界

### 6.1 SearchProvider

保留现有网页搜索协议：

```python
def search(query: str, max_results: int) -> list[SearchResult]
```

### 6.2 DocumentRetriever

新增私有文档检索协议：

```python
def retrieve(query: str, top_k: int) -> list[DocumentResult]
```

真实实现为 `ChromaDocumentRetriever`，测试实现为 `FakeDocumentRetriever`。

### 6.3 EvidenceManager

增加网页和文档两个明确入口：

```python
add_search_results(question, results)
add_document_results(question, results)
```

两种来源共享同一个 `S1/S2/...` 编号序列和12条总上限。

去重规则：

- 网页按规范化URL去重。
- 文档按知识库、文件名、页码和chunk编号形成稳定键去重。

### 6.4 KnowledgeBaseService

负责：

- 验证文件扩展名、数量和大小。
- 为一次入库创建 `knowledge_base_id`。
- 保存原始文件。
- 调用Loader和Splitter。
- 批量请求Embedding。
- 创建并持久化Chroma索引。
- 写入不含密钥的manifest。

它不参与研究问题规划、反思或报告写作。

第一版上传限制固定为：单次最多5个文件、单文件最大10 MiB、总大小最大30 MiB。
限制在读取完整内容前检查，防止超大文件占用过多内存。

## 7. 文档入库流程

```text
POST /knowledge-bases
→ 验证PDF/Markdown
→ 创建knowledge_base_id
→ 保存原始文件
→ Loader生成Document
→ RecursiveCharacterTextSplitter切分
→ 千问Embedding API生成向量
→ 写入本地Chroma
→ 保存manifest
→ 返回文档数、chunk数和ready状态
```

建议初始切分参数：

```python
chunk_size = 800
chunk_overlap = 120
separators = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
```

这些值是可测试的初始配置，不宣称为最佳值。

## 8. Embedding与向量存储

第一版选择：

- 模型：`qwen3.7-text-embedding-flash`。
- 默认维度：1024。
- 调用方式：封装成LangChain `Embeddings` 接口。
- 向量库：`langchain-chroma` 本地持久化。
- 文档向量使用 `embed_documents()`；研究问题使用 `embed_query()`。

程序必须固定模型名称和向量维度。已有知识库不能在不重建索引的情况下更换模型或维度。

## 9. 研究调用流程

研究请求扩展为：

```json
{
  "topic": "企业如何建设RAG知识库？",
  "retrieval_mode": "hybrid",
  "knowledge_base_id": "kb-xxx"
}
```

兼容旧请求：

```json
{"topic": "..."}
```

旧请求默认等价于 `retrieval_mode="web"`。

每个 `ResearchQuestion` 的处理：

```text
web      → TavilySearch
document → ChromaDocumentRetriever
hybrid   → 两者都调用
```

混合模式不直接比较Tavily分数和Chroma分数，而是确定性交替候选来源：

```text
Web1 → Document1 → Web2 → Document2 → ...
```

一侧结果不足时由另一侧补足。两轮研究都使用同样规则。

## 10. API与UI

### 10.1 API

新增：

```text
POST /knowledge-bases
```

扩展：

```text
POST /research
```

知识库不存在、尚未就绪或模式组合非法时返回422，不静默切换知识库。

### 10.2 Streamlit

侧边栏增加：

- PDF/Markdown文件上传。
- `web`、`document`、`hybrid` 模式选择。
- 入库状态、文档数和chunk数反馈。

Evidence页面按来源类型显示：

- 网页：域名、标题和可点击链接。
- 文档：文件名、页码和片段内容，不生成伪链接。

## 11. SQLite与文件持久化

### 11.1 evidence表迁移

新结构允许网页URL为空，并增加：

```text
source_type
document_name
page_number
chunk_index
```

迁移步骤：

1. 在事务内检查当前schema版本。
2. 创建新Evidence表。
3. 将旧数据复制为 `source_type="web"`。
4. 保留现有URL和内容。
5. 替换旧表并更新数据库版本。
6. 验证行数与任务外键关系后提交。

失败必须回滚，不得删除原数据库文件重建。

### 11.2 知识库文件

```text
data/knowledge_bases/{knowledge_base_id}/
├─ documents/
├─ index/
└─ manifest.json
```

`CLAUDE.md`必须先登记该目录用途；`.gitignore`必须排除用户文档和向量索引。

## 12. 报告与引用

`ReportWriter`继续使用 `S1/S2/...` 校验未知编号。

引用展示：

```markdown
- [S1] [网页标题](https://example.com)
- [S2] 企业知识库方案（knowledge-base.pdf，第12页）
- [S3] 系统架构说明（architecture.md）
```

引用编号合法只表示来源存在，不等于结论已经完成事实核查或语义蕴含验证。

## 13. 错误与降级

- 文件类型、大小或数量不符合限制：拒绝入库并指出文件。
- 任一文件解析失败：本次知识库创建失败，不留下可使用的半成品索引。
- 知识库不存在或模型配置不匹配：研究请求返回422。
- Tavily失败但RAG成功：记录网页搜索错误，继续文档研究。
- RAG失败但Tavily成功：记录文档检索错误，继续联网研究。
- 两个来源都没有Evidence：任务标记 `FAILED`，不生成空报告。
- Embedding调用不得把密钥、完整私密文档或供应商原始异常写入日志。

## 14. 配置与安全

计划新增配置名：

```text
DASHSCOPE_API_KEY
DASHSCOPE_BASE_URL
DASHSCOPE_EMBEDDING_MODEL
DASHSCOPE_EMBEDDING_DIMENSION
RAG_TOP_K
RAG_CHUNK_SIZE
RAG_CHUNK_OVERLAP
```

实施时只更新 `.env.example` 和Settings定义，不代替用户填写或修改本地 `.env`。

私有文件、Chroma数据、模型响应原文和API Key不得进入Git、测试夹具或日志。

## 15. 测试与验收

### 15.1 离线测试

- PDF/Markdown Loader正常、空文档和异常路径。
- 中文切分参数与metadata保留。
- Fake Embeddings、Fake Retriever和确定性Top-K。
- 网页与文档Evidence转换、去重、交替和12条上限。
- 三种检索模式。
- 单源失败降级与双源无结果失败。
- SQLite旧schema迁移和旧任务读取。
- 文档引用渲染与未知编号拦截。
- API请求验证和Streamlit冒烟测试。

### 15.2 真实验收

- 上传一份非敏感PDF和一份Markdown。
- 建库成功且重启后索引仍可读取。
- 固定问题命中预期文档片段。
- 混合研究报告同时包含网页和文档来源。
- 报告中的文件名、页码和网页链接正确。
- 完整测试、API启动、UI启动和Docker路径重新验证。
- README补充非敏感截图、运行说明、成本与隐私边界。

## 16. 作品集表述边界

完成上述验收后，可以表述为：

> 在自研研究型Agent中接入LangChain文档加载与切分、千问Embedding API和Chroma持久化向量检索，实现Tavily互联网搜索与私有PDF/Markdown知识库的混合检索，并统一完成Evidence去重、引用校验、失败降级和端到端测试。

不得表述为生产级企业知识库、完整事实核查系统或已验证的大规模高并发RAG平台。
