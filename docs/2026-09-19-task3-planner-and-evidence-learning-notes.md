# Task 3 学习笔记：研究规划与证据管理

> 日期：2026-09-19
> 当前状态：Planner 与 EvidenceManager 已实现；Task 3 测试 8 项通过，完整项目测试 26 项通过；第一轮学习完成。

## 1. Task 3 解决什么问题

Task 3 将统一的 LLM 和搜索结果接口连接到研究流程的前半段：

```text
研究主题
-> Planner生成4个研究问题
-> 搜索服务返回SearchResult
-> EvidenceManager清理、去重和编号
-> 得到可供后续反思与报告使用的Evidence
```

Planner 负责让 LLM 做规划；EvidenceManager 使用确定性 Python 规则管理来源。

## 2. Planner 的输入、处理和输出

### 输入

```python
topic: str
```

### 处理

```text
研究主题
-> 构造system_prompt和user_prompt
-> 调用LLMClient.generate_structured()
-> 要求输出ResearchPlan
-> 检查问题数量必须为4
-> 统一问题文本空白
-> 使用casefold()检查重复
```

四个问题覆盖：背景、证据或替代方案、限制与风险、评估与结果。

### 输出

```python
ResearchPlan
```

`LLMResult.value` 是 `ResearchPlan` 实例。Planner 整理问题后使用 `model_copy(update=...)` 返回新的 `ResearchPlan`，不会把 `LLMResult` 当作计划返回。

### 失败路线

- LLM 调用失败：异常继续交给调用层。
- 返回的计划不是4个问题：抛出 `ValueError`。
- 规范化后出现重复问题：抛出 `ValueError`。

## 3. EvidenceManager 的内部状态

```python
self.max_sources: int
self._evidence: list[Evidence]
self._seen_urls: set[str]
```

可以按三部分读取类型标注和赋值：

```text
self._evidence : list[Evidence] = []
属性名          类型标注          实际值
```

- `_evidence` 保存有顺序的完整 `Evidence` 对象。
- `_seen_urls` 只保存已采用的 URL，用于快速判断重复。
- `max_sources` 是整个研究任务累计的来源上限，不是单次 `add()` 的上限。

## 4. 从 SearchResult 转换为 Evidence

`add()` 接收：

```python
question: ResearchQuestion
results: list[SearchResult]
```

每条搜索结果按以下顺序处理：

```text
检查累计来源上限
-> 清理URL
-> 判断URL是否已经见过
-> 创建Evidence实例
-> 登记URL
-> 保存Evidence
```

创建对象时的数据来源：

```python
evidence = Evidence(
    source_id=f"S{len(self._evidence) + 1}",
    question_id=question.id,
    title=result.title,
    url=normalized_url,
    content=result.content,
)
```

一条 `Evidence` 是一个来源对象，内部包含5个字段：

```text
source_id   来源编号，如S1
question_id 对应的研究问题编号
title       来源标题
url         清理后的地址
content     来源内容
```

“保存3个来源”表示列表中有3个 `Evidence` 对象，不是只有3个字段。

## 5. URL 清理与去重

URL 规范化会：

- 将协议和域名转成小写；
- 删除 `utm_*`、`fbclid`、`gclid`；
- 删除 `#summary` 等片段；
- 保留有业务意义的查询参数。

```python
if normalized_url in self._seen_urls:
    continue
```

表示已经使用过的 URL 跳过当前循环。

```python
self._seen_urls.add(normalized_url)
```

这里调用的是 Python 集合 `set` 的 `add()` 方法，作用是登记已经采用的 URL。它不同于 `manager.add(question, results)`：点号前面的对象不同，调用的方法也不同。

## 6. break、continue 与 return

```text
continue -> 跳过当前循环，进入下一轮
break    -> 结束最近的整个循环，继续执行循环后面的代码
return   -> 结束整个函数并返回结果
raise    -> 中断正常路线并向调用层传播异常
```

达到来源上限时执行 `break`，不会报错，也不会终止整个程序；循环结束后仍会执行 `return added`。

## 7. 本次新增与全部证据

```python
added = manager.add(question, results)
all_evidence = manager.all()
```

- `added`：本次调用新增加的 `list[Evidence]`。
- `manager.all()`：Manager 从创建以来保存的全部证据列表副本。

`all()` 是 `EvidenceManager` 自己定义的方法：

```python
def all(self) -> list[Evidence]:
    return list(self._evidence)
```

返回副本可以避免外部代码直接修改 Manager 内部列表。

## 8. 测试证明什么

Planner 测试证明：

- 返回4个不重复问题；
- 拒绝不足4个的问题；
- 统一多余空白；
- 拒绝规范化后的重复问题。

EvidenceManager 测试证明：

- 跟踪参数清理后能够识别重复 URL；
- 删除 URL 片段及 `utm_*`、`fbclid`、`gclid`；
- 跨多次 `add()` 仍然全局去重并连续编号；
- 达到累计来源上限后停止添加。

## 9. 掌握标准

不要求背源码，但应当能够说明：

1. Planner 为什么返回 `ResearchPlan`，而不是 `LLMResult`；
2. 为什么问题数量和去重规则由 Python 再检查一次；
3. `SearchResult` 如何转换为 `Evidence`；
4. `_evidence` 列表和 `_seen_urls` 集合分别保存什么；
5. `manager.add()`、`set.add()` 和 `manager.all()` 的区别；
6. 来源上限为什么跨多次调用累计。

下一步进入 Task 4：执行第一轮搜索，根据证据反思信息缺口，并最多进行一次补充搜索。
