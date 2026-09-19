# Task 2 学习笔记：LLM 与搜索服务边界

> 日期：2026-09-14
> 初次整理：2026-09-14；完成复盘：2026-09-18
> 当前状态：Task 2 代码已实现并通过测试；第一轮学习与整体复盘已完成。
> 已学习：FakeLLM、FakeSearch、DeepSeekLLM、TavilySearch、依赖注入、结构化输出、重试、用量统计与异常传播。

## 1. Task 2 解决什么问题

Task 2 给后续 Agent 提供两类统一接口：

```text
LLM输入：system_prompt + user_prompt + output_type
LLM输出：LLMResult（结构化对象 + 调用用量）

搜索输入：query + max_results
搜索输出：list[SearchResult]
```

测试和真实运行使用相同接口：

```text
测试：FakeLLM / FakeSearch
真实：DeepSeekLLM / TavilySearch
```

后续 Agent 只依赖统一接口，不需要了解 DeepSeek 或 Tavily 的内部字段。这叫“隔离外部服务”。

## 2. FakeLLM

### 作用

FakeLLM 不调用真实模型。测试人员提前准备结果，它每次被调用时按顺序返回下一条。

```python
plan1 = ResearchPlan(...)
plan2 = ResearchPlan(...)
llm = FakeLLM([plan1, plan2])
```

类型层级：

```text
plan1                    -> ResearchPlan 实例
[plan1, plan2]           -> list
deque([plan1, plan2])    -> deque
ResearchPlan             -> 类本身
```

### 每次调用

```python
result = llm.generate_structured(
    "Return JSON.",
    "Research AI agents.",
    ResearchPlan,
)
```

参数含义：

```text
system_prompt -> 模型的工作规则
user_prompt   -> 本次具体任务
output_type   -> 期望的输出类，这里是 ResearchPlan
```

FakeLLM 当前不会使用两个 Prompt 生成内容，但必须保留它们，才能与 DeepSeekLLM 保持相同接口。

### 处理过程

```text
检查 responses 是否为空
-> popleft() 取出并删除队首结果
-> isinstance(value, output_type) 检查类型
-> 创建 Usage(llm_requests=1)
-> 返回 LLMResult
```

`popleft()` 不需要写在 FakeLLM 的循环里。外部每调用一次 `generate_structured()`，它就取出一条预设结果；后续 Agent 决定调用多少次。

## 3. 类、实例和内部属性

```python
isinstance(plan1, ResearchPlan)
```

问的是“`plan1` 是否是 `ResearchPlan` 的实例”，不是比较二者是否相等。

```text
ResearchPlan       -> 类
plan1              -> ResearchPlan 实例
plan1.topic        -> str
plan1.questions    -> list
plan1.questions[0] -> ResearchQuestion 实例
plan1.model_dump() -> dict
```

对象里面包含字符串或列表，不代表整个对象就是字符串或列表：

```python
isinstance(plan1, ResearchPlan)       # True
isinstance(plan1, str)                # False
isinstance(plan1.topic, str)          # True
isinstance(plan1.questions, list)     # True
```

## 4. 对象、字典、列表和 JSON 的访问方式

```text
Python 对象属性：result.usage.llm_requests
Python 字典键：data["usage"]["llm_requests"]
Python 列表元素：items[0]
JSON 字符串：先 json.loads()，再按字典访问
```

`LLMResult` 的字段定义是：

```python
value: ModelT
usage: Usage
```

因此使用小写属性名：

```python
result.usage.llm_requests
```

不能写 `result.Usage`；`Usage` 是类名，不是 `result` 的属性名。

## 5. FakeSearch

### 作用

FakeSearch 根据查询词从预设字典中读取搜索结果：

```python
search = FakeSearch({
    "python": [result1, result2, result3]
})
```

```text
键 "python"                   -> 查询词
值 [result1, result2, result3] -> 搜索结果列表
```

### 处理过程

```python
value = self.responses.get(query, [])
return list(value[:max_results])
```

```text
query.strip()             -> 检查空查询
dict.get(query, [])       -> 按查询词取结果；键不存在时返回 []
value[:max_results]       -> 最多取指定数量
list(...)                 -> 统一返回普通列表
```

FakeSearch 只读取和切片，不删除原字典中的结果。连续搜索同一个 query 可以重复得到相同结果。

## 6. TavilySearch 与依赖注入

TavilySearch 需要一个能执行搜索的客户端。这个客户端可以由外部传入，也可以根据 API Key 创建。

```text
外部传入 client
-> 直接保存为 self.client
-> 用于离线测试

没有 client，但有 api_key
-> 创建真实 TavilyClient
-> 保存为 self.client

client 和 api_key 都没有
-> raise ValueError
-> 对象创建失败
```

依赖注入不是筛选数据，而是：

> 类需要另一个对象工作时，允许这个依赖从外部传入，不把具体实现完全写死。

因此测试可以注入 `_FakeTavilyClient`，真实运行可以使用 `TavilyClient`。

## 7. Tavily 原始字典转换

Tavily 原始返回近似为：

```python
response = {
    "results": [
        {
            "title": "Tavily docs",
            "url": "https://docs.tavily.com",
            "content": "Official documentation.",
            "score": 0.91,
        }
    ]
}
```

转换路线：

```text
response：dict
-> response.get("results", [])：list
-> item：dict
-> SearchResult(...)：SearchResult 对象
-> 最终：list[SearchResult]
```

列表推导式的最外层是 `[]`，所以整个返回值是列表；列表中的每个元素才是 `SearchResult` 对象。

## 8. `.get()`、假值和 `or`

```python
response.get("results", [])
```

表示：字典中存在 `"results"` 就返回对应值；键不存在就返回默认空列表。它不会修改原字典。

注意：键存在但值是 `None` 时，`.get()` 返回 `None`，不会使用默认值。

这些值在布尔判断中被视为假：

```python
""
[]
{}
None
0
False
```

但它们本身不会都变成 `False`：

```text
""   仍是 str
[]   仍是 list
{}   仍是 dict
None 仍是 NoneType
```

`or` 返回的是原值之一，不一定返回布尔值：

```python
"" or "Untitled source"       # "Untitled source"
None or ""                    # ""
"Python" or "Default"        # "Python"
[] or ["default"]             # ["default"]
```

## 9. 正常路线与异常路线

```text
正常路线：
调用函数 -> 验证成功 -> 继续执行 -> return 正常结果

异常路线：
调用函数 -> raise 异常 -> 跳过当前调用链尚未执行的代码
-> 沿调用栈向上寻找匹配的 except
```

`raise` 不是 `return`：

```text
return -> 正常结束函数并交还一个值
raise  -> 异常结束函数并向上交出异常对象
```

`try` 划定异常保护范围，`except` 处理匹配异常。普通同步调用中，无论异常来自直接调用还是多层间接调用，只要发生在 `try` 的动态调用链中并且没有被中间层处理，外层 `except` 就可以捕获。

已经执行过的代码不会撤销；异常发生以后、尚未执行的正常代码会被跳过。捕获完成后，可以从整个 `try...except` 后面的公共代码继续。

### 当前 TavilySearch 的异常路线

```text
空 query
-> try 之前 raise ValueError
-> 当前方法下面的 except 捕获不到
-> 交给调用 TavilySearch.search() 的上层处理

缺少 url 或 URL 不合法
-> KeyError / ValueError
-> 原样继续向上抛

连接失败等其他异常
-> 转换成统一的 SearchError
-> 保留底层异常原因链
```

## 10. 当前需要达到的掌握标准

不要求背源码。能够用自己的话回答下面问题即可：

1. 为什么测试时使用 FakeLLM 和 FakeSearch？
2. `ResearchPlan` 类与 `plan1` 实例有什么区别？
3. 为什么 `output_type` 传 `ResearchPlan`，而不是 `plan1`？
4. FakeLLM 为什么使用 `deque` 和 `popleft()`？
5. FakeSearch 为什么使用字典和查询词？
6. Tavily 字典怎样转换成 `list[SearchResult]`？
7. `raise` 后正常路线发生什么？
8. 为什么 `self.client = client` 是两条成功路线的汇合点？

## 11. DeepSeekLLM 的正常路线

真实 LLM 适配器接收三项输入：

```text
system_prompt -> 系统规则字符串
user_prompt   -> 本次任务字符串
output_type   -> 期望输出的 Pydantic 类，例如 ResearchPlan
```

两段提示词先组成 SDK 需要的消息列表：

```python
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt},
]
```

真实调用入口：

```python
response = self.client.chat.completions.create(...)
```

这里 `client.chat.completions.create()` 是 SDK 提供的请求工具；`response` 才是请求返回的数据。

返回内容的访问路线：

```text
response
-> response.choices：list
-> response.choices[0]：第一个候选答案对象
-> .message：消息对象
-> .content：str
```

随后：

```python
content = response.choices[0].message.content
value = output_type.model_validate_json(content)
```

当 `output_type` 是 `ResearchPlan` 时，第二行相当于：

```python
value = ResearchPlan.model_validate_json(content)
```

完整正常路线：

```text
提示词字符串
-> messages 列表
-> SDK 请求
-> response 对象
-> content JSON 字符串
-> Pydantic 验证
-> ResearchPlan 实例
-> 与 Usage 一起装入 LLMResult
```

## 12. SimpleNamespace 与 SDK 假对象

`SimpleNamespace` 是 Python 标准库 `types` 模块中的类，适合在测试中快速创建能够使用点号访问属性的简单对象：

```python
response = SimpleNamespace(
    choices=[
        SimpleNamespace(
            message=SimpleNamespace(content="...")
        )
    ],
    usage=SimpleNamespace(
        prompt_tokens=120,
        completion_tokens=80,
    ),
)
```

它模仿了真实 SDK 返回对象的访问形状：

```python
response.choices[0].message.content
response.usage.prompt_tokens
```

正式调用时不需要自己创建 `SimpleNamespace`；真实 SDK 会创建自己的响应对象。项目的重要业务数据继续使用 Pydantic 模型进行验证。

## 13. 最多两次请求与无效 JSON 重试

```python
for attempt in range(2):
```

`attempt` 依次为 `0` 和 `1`，表示最多请求两次。限制次数不代表第二次一定成功，只是阻止无限重试。

```python
try:
    value = output_type.model_validate_json(content)
except ValidationError:
    if attempt == 0:
        continue
    raise
```

三种有效路线：

```text
第一次成功
-> 立即 return
-> 实际请求1次，第二次不执行

第一次失败、第二次成功
-> 第一次 continue
-> 第二次 return
-> 实际请求2次

两次都失败
-> 第一次 continue
-> 第二次执行裸 raise
-> 原 ValidationError 向调用层传播
```

第一次成功、第二次失败以及两次都成功，在当前代码中不会发生，因为第一次成功后已经 `return`，函数结束。

每次请求的 Token 都先累加，因此第一次无效响应也会计入用量：

```text
第一次：输入10，输出2
第二次：输入20，输出10
最终：输入30，输出12，请求2次
```

## 14. Task 2 的异常分类

```text
content 为空
-> raise ValueError

JSON 或字段验证失败
-> 第一次重试
-> 第二次裸 raise 原 ValidationError

网络、SDK 等其他异常
-> 包装成 LLMError("DeepSeek request failed")
-> 使用 from error 保留原始原因链
```

`try...except` 只负责捕获异常，不保证程序继续。捕获后可以选择默认值、`continue`、`return` 或再次 `raise`。

裸 `raise` 只能在处理异常的上下文中使用，表示把当前异常对象原样继续向调用层传播，保留其类型、字段详情和 traceback。

“上一层”由函数实际调用栈决定，而不是由缩进决定：

```text
model_validate_json()
-> generate_structured()
-> Planner
-> 后续应用服务
```

沿途第一个匹配的 `except` 可以处理异常；如果一直没有匹配处理，当前程序或请求最终失败并显示 traceback。

## 15. Task 2 完成后的整体接口

```text
测试 LLM：FakeLLM
真实 LLM：DeepSeekLLM
共同方法：generate_structured(...)

测试搜索：FakeSearch
真实搜索：TavilySearch
共同方法：search(...)
```

Task 3 可以只依赖这些统一接口，不需要知道测试或真实提供方内部如何工作。

Task 3 的 Research Planner 与 Evidence Manager 已完成。下一步进入 Task 4：第一轮搜索、反思与有限第二轮。
