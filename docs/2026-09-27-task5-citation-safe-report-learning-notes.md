# Task 5：引用安全报告学习笔记

> 整理日期：2026-09-27
> 当前状态：报告模块已实现；本文只保留理解完整调用链所需的核心内容，不要求背诵源码。

## 1. Task 5 解决什么问题

搜索和反思得到的 `Evidence` 还不是最终报告。Task 5 负责让 LLM 根据已知证据写出草稿，再由普通 Python 代码验证引用、生成参考文献，并提供 Markdown 与 HTML 两种结果。

```text
topic + ResearchPlan + list[Evidence]
                ↓
           ReportWriter
                ↓ 调用 LLM
            ReportDraft
                ↓ 引用校验与整理
          ResearchReport
```

LLM 负责写作；确定性代码负责可信来源、引用检查和输出转换。

## 2. 关键文件与职责

- `src/mini_researcher/report.py`：报告草稿格式、引用验证、参考文献和 HTML 渲染。
- `src/mini_researcher/models.py`：正式 `ResearchReport` 数据模型。
- `src/mini_researcher/llm.py`：真实 LLM 把 JSON 字符串解析成调用方指定的 Pydantic 实例。
- `tests/fakes.py`：测试时从预设队列取出已创建的实例，不访问真实 LLM。
- `tests/test_report.py`：验证正常报告、未知引用、模型漏报和 HTML 安全。

## 3. ReportDraft 与 ResearchReport

`ReportDraft` 是 LLM 刚生成、尚未验证的草稿：

```python
class ReportDraft(BaseModel):
    title: str
    markdown: str
    used_source_ids: list[str]
```

`ResearchReport` 是通过引用检查后交给后续服务、数据库或页面的正式结果：

```python
class ResearchReport(BaseModel):
    title: str
    markdown: str
    html: str | None
    used_source_ids: list[str]
```

`draft.markdown` 当前是采用 Markdown 语法的字符串，还不是磁盘上的 `.md` 文件。

## 4. Evidence 编号从哪里来

`EvidenceManager` 使用普通 Python 代码按保存顺序生成 `S1`、`S2`：

```python
source_id=f"S{len(self._evidence) + 1}"
```

`ReportWriter` 再将编号、标题、URL 和内容拼成 Evidence Catalog，放入 `user_prompt`。LLM 只能引用目录中已经存在的编号，不负责创造可信编号。

## 5. FakeLLM 与真实 LLM 的两条路线

测试路线：

```text
测试先创建 ReportDraft 实例
→ 放入 FakeLLM 的预设队列
→ 每次 generate_structured 取出一条
→ isinstance 检查类型
→ 包装成 LLMResult
```

真实路线：

```text
DeepSeek 返回 JSON 字符串 content
→ output_type.model_validate_json(content)
→ 得到 ReportDraft 实例
→ 包装成 LLMResult
```

`output_type: type[ModelT]` 中，`output_type` 是参数名，`type[ModelT]` 是类型标注。调用时传入 `output_type=ReportDraft`，函数内部才能执行 `ReportDraft.model_validate_json(content)`。

## 6. 引用检查的四步

```python
known_source_ids = {item.source_id for item in evidence}
markdown_source_ids = list(
    dict.fromkeys(_CITATION_PATTERN.findall(draft.markdown))
)
used_source_ids = list(
    dict.fromkeys([*draft.used_source_ids, *markdown_source_ids])
)
unknown_source_ids = sorted(set(used_source_ids) - known_source_ids)
```

含义：

1. `known_source_ids`：Evidence 中真实存在的可信编号。
2. `markdown_source_ids`：程序从报告正文中实际扫描到的编号。
3. `used_source_ids`：模型主动声明的编号，加上正文中模型漏报的编号，并保留顺序。
4. `unknown_source_ids`：报告使用了、但 Evidence 中不存在的编号。

集合减法只保留左边有、右边没有的元素：

```python
{"S1", "S3"} - {"S1", "S2"} == {"S3"}
```

`S1` 通过检查；`S2` 是可用但未使用的来源；`S3` 是未知引用。发现未知引用时拒绝整份报告，不是静默删除编号。

## 7. 为什么不能只相信 used_source_ids

`draft.markdown` 与 `draft.used_source_ids` 都由 LLM 生成，可能不一致：

```python
draft.markdown = "结论。[S1]"
draft.used_source_ids = []
```

因此程序必须重新扫描正文。反过来，如果正文藏有 `[S9]` 而模型只声明 `S1`，正文扫描也能发现假引用。

## 8. MarkdownIt 的作用

`MarkdownIt` 来自第三方依赖 `markdown-it-py`，不是 Python 标准库。它把 Markdown 字符串渲染成网页可展示的 HTML：

```python
MarkdownIt("commonmark", {"html": False}).render(markdown_text)
```

`html=False` 禁止把 LLM 输出的原始 HTML 当作可执行 HTML，降低脚本注入风险。

## 9. 输入、处理、输出和失败

输入：

```text
topic: str
plan: ResearchPlan
evidence: list[Evidence]
```

处理：

```text
构造 Evidence Catalog
→ 调用 LLM 得到 ReportDraft
→ 扫描并验证引用
→ 生成参考文献
→ Markdown 转 HTML
```

输出：

```text
ResearchReport
```

主要失败路径：

- LLM 请求或 JSON 验证失败：由 LLM 适配层抛出异常。
- 报告引用不存在的编号：抛出 `InvalidCitationError`。
- 草稿字段为空或类型错误：Pydantic 验证失败。

## 10. 掌握标准

进入 Task 6 前，不要求背源码，但应当能说明：

1. Evidence 编号由谁创建，大模型为什么不能随意创建可信编号；
2. `ReportDraft` 和 `ResearchReport` 的区别；
3. FakeLLM 为什么不需要 JSON 转换；
4. `output_type` 如何决定真实 LLM 返回实例的类型；
5. 为什么既检查模型声明，也重新扫描 Markdown 正文；
6. 发现未知引用时为什么拒绝报告而不是静默删除。
