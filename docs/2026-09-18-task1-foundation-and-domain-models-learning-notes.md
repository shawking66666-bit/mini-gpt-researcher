# Task 1 学习笔记：项目基础与领域模型

> 初次整理：2026-09-18
> 当前状态：Task 1 代码已实现并通过测试；本文用于后续整体复盘，不要求背诵源码。

## 1. Task 1 解决什么问题

Task 1 先建立项目运行需要的配置和核心数据格式。后续的规划、搜索、证据、报告和任务状态，都要使用这些统一模型传递数据。

```text
环境变量 -> Settings
研究主题与问题 -> ResearchPlan / ResearchQuestion
搜索结果 -> SearchResult
可引用资料 -> Evidence
调用用量 -> Usage
最终报告 -> ResearchReport
完整任务状态 -> ResearchState
```

## 2. Python 包和本地导入

项目采用 `src` 布局：

```text
src/
└── mini_researcher/
    ├── __init__.py
    ├── config.py
    └── models.py
```

`mini_researcher` 是本地 Python 包，`models.py` 是包中的模块，`ResearchPlan` 是模块中的类：

```python
from mini_researcher.models import ResearchPlan
```

可以读成：

```text
从 mini_researcher 包
找到 models 模块
导入 ResearchPlan 类
```

导入不要求代码先上传到 PyPI。本地包只要位于当前解释器能够找到的导入路径中，就可以被导入。

## 3. 解释器与虚拟环境

虚拟环境为当前项目提供隔离的 Python 解释器和依赖目录：

```text
.venv/
├── Scripts/python.exe
├── Scripts/pip.exe
└── Lib/site-packages/
```

如果 Pydantic 安装在项目 `.venv` 中，但 VS Code 选择了全局 Python，运行时可能找不到 Pydantic。因此需要让编辑器、终端和测试尽量使用同一个虚拟环境解释器。

`Scripts` 不只是“存放项目需要的包”。包通常安装在 `Lib/site-packages`；`Scripts` 主要存放 Python、pip、pytest 等可执行入口和环境激活脚本。

## 4. 类、实例与 Pydantic 模型

```python
class ResearchPlan(BaseModel):
    topic: str = Field(min_length=3)
    questions: list[ResearchQuestion] = Field(min_length=1, max_length=4)
```

这里：

```text
ResearchPlan                 -> 子类
BaseModel                    -> 父类，提供初始化、验证和转换能力
topic: str                   -> Python 类型标注
questions: list[...]         -> Python 类型标注
Field(...)                   -> 额外验证规则
```

`BaseModel` 本身没有 `topic` 和 `questions`。这两个字段由 `ResearchPlan` 自己声明；Pydantic 读取声明后，让模型能够接收、验证并保存具体值。

```python
plan = ResearchPlan(
    topic="AI agents",
    questions=[question],
)
```

类型层级：

```text
ResearchPlan             -> 类
plan                     -> ResearchPlan 实例
plan.topic               -> str
plan.questions           -> list
plan.questions[0]        -> ResearchQuestion 实例
```

普通类只有 `topic: str` 时，Python主要记录类型标注，不会自动给实例生成具体值；Pydantic 的 `BaseModel` 会进一步把标注处理成模型字段。

## 5. 继承与实例初始化

继承语法：

```python
class Child(Parent):
    ...
```

类名后面的括号写父类，不是字段。创建实例时的括号才传入具体数据：

```python
plan = ResearchPlan(topic="AI agents", questions=[question])
```

普通类通常在 `__init__()` 中保存实例数据：

```python
class Person:
    def __init__(self, name: str):
        self.name = name
```

```python
person = Person("xj")
```

`self.name = name` 把传入值保存为当前实例的属性。Pydantic 模型没有手写同样的 `__init__()`，因为 `BaseModel` 已经提供了相应机制。

## 6. 核心模型及其职责

### ResearchQuestion

保存一个研究子问题：

```text
id            -> 问题编号
text          -> 问题文本
round_number  -> 属于第几轮研究，默认1，最多2
```

### ResearchPlan

保存研究主题和1到4个研究问题。

### SearchResult

保存搜索提供方返回的一条结果：标题、URL、正文摘要和可选分数。

### Evidence

保存经过项目整理、可以被报告引用的证据。`source_id` 使用 `S1`、`S2` 等格式，并记录它属于哪个研究问题。

### Usage

统计 LLM 请求次数、搜索次数、输入输出 Token、Tavily 用量和估算成本。

### ResearchReport

保存报告标题、Markdown、可选 HTML 和实际使用的来源编号。

### ResearchState

汇总一次研究任务的完整状态，包括阶段、轮次、计划、证据、错误、用量和报告。

## 7. 对象、字典与 JSON 转换

```python
plan.model_dump()
```

将 Pydantic 实例转换为 Python 字典。

```python
plan.model_dump_json()
```

将 Pydantic 实例转换为 JSON 字符串。

```python
ResearchPlan.model_validate_json(json_string)
```

解析并验证 JSON 字符串，成功后得到 `ResearchPlan` 实例。

```text
ResearchPlan 实例
├── model_dump() -> dict
└── model_dump_json() -> str

JSON 字符串
└── model_validate_json() -> ResearchPlan 实例
```

## 8. 配置模型

配置模块负责从环境变量读取 DeepSeek、Tavily、数据库路径、循环上限等设置。配置与业务模型分开，可以避免在代码中写死密钥和运行参数。

密钥只通过环境变量或本地 `.env` 提供，不进入代码、测试输出或 Git。

## 9. 测试证明什么

Task 1 的测试主要证明：

- 配置能够从环境变量读取；
- 缺少必要配置时能够明确失败；
- 模型能够接受正确数据；
- 字段长度、轮次和 URL 规则能够阻止错误数据；
- 默认列表和默认 Usage 不会被多个实例错误共享。

## 10. 掌握标准

进入后续任务前，不要求背源码，但应当能够说明：

1. 包、模块、类和实例分别是什么；
2. 为什么项目使用虚拟环境；
3. `BaseModel` 提供什么，子类自己声明什么；
4. `topic: str` 在普通类与 Pydantic 模型中的差异；
5. `model_dump()`、`model_dump_json()` 和 `model_validate_json()` 的方向；
6. `ResearchState` 为什么需要集中保存一次任务的状态。
