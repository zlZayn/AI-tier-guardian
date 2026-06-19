# Architecture

本文档记录 tier-guardian 的文件依赖关系、组件间数据流、仲裁决策矩阵和关键技术选型。与 README 的分工：**README 回答"这是什么、怎么用"；本文档回答"里面怎么串通的、改了哪里会影响到什么"。**

---

## 核心抽象

### 四节点与三层分工

四个审查员的协作方式：**A 和 B 在 Layer 1 互不知情地并行工作，各自得出初步结论后交给程序（pre_filter）决定是否放行；没放行的进入 Layer 2 交给 C 做深度判断，C 的结论再交给程序（deep_judge）裁决最终动作；只有落到"人工复审"的案子，D 才会出场整理材料供人审阅。** 核心原则是"AI 只做语义判断，程序做所有仲裁"——四名审查员之间不直接对话，每个节点的输出都是给仲裁程序读的，不是给下一个 AI 读的。

| 节点 | 做什么 | thinking | 触发条件 |
| :--- | :--- | :-: | :--- |
| A — surface_scanner | 字面模式匹配，不推理意图 | 关 | 始终 |
| B — intent_probe | 沟通意图分类 | 关 | 始终 |
| C — context_judge | 结合中文文化语境判定违规 | 开 | A/B 未直接 PASS |
| D — evidence_summarizer | 整理摘要供人工复核，不重新判断 | 关 | 仅 HUMAN_REVIEW |

### 组件边界

```text
orchestrator (中央编排器)
  ├─ LLMClient          ← 封装 OpenAI SDK，所有 AI 节点共享
  ├─ CacheManager       ← 封装 diskcache，两层孤立缓存
  ├─ nodes/*.py         ← 四个 AI 节点函数，各自接收独立输入
  ├─ arbitration.py     ← pre_filter + deep_judge，纯程序
  └─ prompts.py         ← 四个 Prompt 的定义源，节点只读消费
```

- **AI 节点**（A/B/C/D）各自接收独立输入，返回结构化输出，彼此零依赖
- **仲裁函数**（pre_filter / deep_judge）是纯程序逻辑，不调 LLM
- **Orchestrator** 是唯一的编程序列定义者，所有调用关系在 `process()` 方法中硬编码

### 数据契约

所有节点间传值通过 TaskContext 聚合：

```text
TaskContext
  ├─ text: str                ← 原始输入
  ├─ scene: str               ← 场景（comment / post 等）
  ├─ nodes.surface            ← SurfaceScannerOutput | None   来自 nodes/surface_scanner.py
  ├─ nodes.intent             ← IntentProbeOutput | None      来自 nodes/intent_probe.py
  ├─ nodes.judge              ← ContextJudgeOutput | None     来自 nodes/context_judge.py
  ├─ nodes.summary            ← EvidenceSummarizerOutput | None 来自 nodes/evidence_summarizer.py
  └─ final_decision           ← FinalDecision | None          来自 arbitration.py
```

每个节点输出是独立的 dataclass，定义在 `models.py`。Orchestrator 在 process() 中逐个填充，仲裁函数读其中若干字段做决策。

各节点 input/output 详细契约：

#### A — surface_scanner

```text
输入: LLMClient, text, locale, Config
输出: SurfaceScannerOutput
        ├─ patterns: list[PatternHit]  最多 5 条
        │     每条约束: fragment 是原文精确子串，span 与之长度一致
        └─ surface_risk: SurfaceRisk   low | medium | high
降级: patterns=[], surface_risk=MEDIUM
```

#### B — intent_probe

```text
输入: LLMClient, text, scene, Config
输出: IntentProbeOutput
        ├─ intent: IntentLabel   7 选 1
        └─ confidence: float     0.0~1.0
降级: intent=OTHER, confidence=0.0
```

#### C — context_judge

```text
输入: LLMClient, text, locale, surface_flags, claimed_intent, Config
输出: ContextJudgeOutput
        ├─ violation: Violation
        │      ├─ is_violation: bool
        │      ├─ type: str | None   非违规时为 None
        │      ├─ severity: ViolationSeverity | None  非违规时为 None
        │      └─ confidence: float
        ├─ reasoning_summary: str     1-2 句结论摘要，非推理过程
        └─ rule_ids: list[str]
降级: is_violation=False, confidence=0.0, reasoning_summary=""
```

#### D — evidence_summarizer

```text
输入: LLMClient, text, surface_risk, intent, judge_output, similar_cases, Config
输出: EvidenceSummarizerOutput
        ├─ one_liner: str             一句话摘要
        ├─ highlight_ranges: list[list[int]]  字符索引对
        ├─ similar_cases: list[SimilarCase]
        └─ suggested_action: str      建议动作
约束: 不得重新判断，不得反驳上游，不得添加原文没有的信息
降级: 最小 fallback 摘要
```

---

## 源码结构

### 目录树与职责

```text
tier_guardian/
├── __init__.py              # 包导出：Config, Orchestrator
├── config.py                # 枚举 + Config/NodeConfig 数据类
├── models.py                # TaskContext + 四节点输出模型
├── prompts.py               # 四个 Prompt 对象的唯一定义处
├── llm_client.py            # OpenAI SDK 包装 + JSON 修复器
├── cache.py                 # diskcache 包装，两层缓存
├── arbitration.py           # pre_filter + deep_judge 纯程序仲裁
├── orchestrator.py          # process() 定义全链路序列
├── cli.py                   # 命令行：单条 / 文件 / REPL
└── nodes/
    ├── surface_scanner.py       # A: 字面模式扫描
    ├── intent_probe.py          # B: 意图分类
    ├── context_judge.py         # C: 深度语境裁决
    └── evidence_summarizer.py   # D: 证据摘要

tests/
├── test_arbitration.py
├── test_cache.py
├── test_llm_client.py
└── test_models.py

根目录
├── config.json              # 运行时配置
├── run_batch.py             # 批量审核 / 集成测试工具
```

### 文件依赖图

箭头方向为 `A → B` 表示 A 导入 B。

```text
入口文件
  run_batch.py → tier_guardian/orchestrator.py
  cli.py       → tier_guardian/orchestrator.py

包导出
  __init__.py → Config, Orchestrator

内核层
  orchestrator.py → config.py
                  → models.py
                  → cache.py
                  → llm_client.py
                  → arbitration.py
                  → nodes/*.py         (四个节点函数)
                  → prompts.py         (提示词注册)

  nodes/*.py     → prompts.py          (取对应 Prompt)
                 → config.py           (取 NodeConfig)
                 → llm_client.py       (调 LLM)

数据模型
  models.py → config.py                (引用枚举类型)

缓存
  cache.py → config.py

LLM 封装
  llm_client.py → config.py

仲裁
  arbitration.py → config.py, models.py

提示词（纯数据，无外部依赖）
  prompts.py → (无)

配置（纯数据，无外部依赖）
  config.py → (无)
```

---

## 请求生命周期

一次 `orch.process(text)` 调用，经过哪些文件、每步做了什么：

### Step 0 — 缓存查寻

```text
orchestrator.py process() [L56-69]
  └─ CacheManager.get_request_cache(text, scene, locale)
     └─ cache.py [L49-79]
        构建 key = SHA256(json({text, scene, locale, schema_version}))
        → diskcache.get(key)
        → 命中则跳过全流程
```

### Step 1 — Layer 1 并行

```text
orchestrator.py _run_layer1() [L107-130]
  └─ ThreadPoolExecutor(2).submit:
       ├─ _run_surface_with_cache(text, locale)
       │    ├─ CacheManager.get_node_cache("surface_scanner", ...)
       │    │  └─ cache.py [L81-94]
       │    └─ run_surface_scanner(llm, text, locale, config)
       │       └─ nodes/surface_scanner.py
       │          ├─ SURFACE_SCANNER.system_prompt   ← prompts.py
       │          ├─ config.surface_scanner           ← 取 NodeConfig
       │          └─ LLMClient.chat(...)              ← llm_client.py
       │
       └─ _run_intent_with_cache(text, scene)
            ├─ CacheManager.get_node_cache("intent_probe", ...)
            └─ run_intent_probe(llm, text, scene, config)
               └─ nodes/intent_probe.py
                  ├─ INTENT_PROBE.system_prompt   ← prompts.py
                  ├─ config.intent_probe          ← 取 NodeConfig
                  └─ LLMClient.chat(...)           ← llm_client.py
```

### Step 2 — 前置仲裁

```text
orchestrator.py process() [L76-82]
  └─ pre_filter(surface_risk, intent)
     └─ arbitration.py [L18-42]
        纯 Python 判定，不调 LLM
        → Layer1Result.PASS  → 直接返回
        → Layer1Result.LAYER2 → 继续
```

### Step 3 — Layer 2 串行

```text
orchestrator.py _run_layer2() [L150-166]
  ├─ CacheManager.get_node_cache("context_judge", ...)
  └─ run_context_judge(llm, text, locale, surface_flags, claimed_intent, config)
     └─ nodes/context_judge.py
        ├─ CONTEXT_JUDGE.system_prompt   ← prompts.py
        ├─ config.context_judge          ← 取 NodeConfig
        └─ LLMClient.chat(...)           ← llm_client.py
```

### Step 4 — 深度仲裁

```text
orchestrator.py process() [L90-91]
  └─ deep_judge(violation, config)
     └─ arbitration.py [L45-71]
        纯 Python 判定
        → PASS / BLOCK → 写回缓存，返回
        → HUMAN_REVIEW → 继续 Step 5
```

### Step 5 — Layer 3 按需

```text
orchestrator.py _run_summary() [L168-185]
  └─ run_evidence_summarizer(llm, text, surface_risk, intent, judge_output, [], config)
     └─ nodes/evidence_summarizer.py
        ├─ EVIDENCE_SUMMARIZER.system_prompt   ← prompts.py
        ├─ config.evidence_summarizer           ← 取 NodeConfig
        └─ LLMClient.chat(...)                  ← llm_client.py
```

### Step 6 — 写回缓存

```text
orchestrator.py _cache_result() [L193-203]
  └─ CacheManager.set_request_cache(text, scene, locale, {final_decision})
     └─ cache.py [L77-79]
```

### 降级链路

每个 AI 节点失败都不会阻断流程，由 orchestrator 在对应 future 上捕获异常。

| 节点 | 降级输出 | 影响 | 代码位置 |
| :--- | :--- | :--- | :--- |
| A | surface_risk=MEDIUM | 必然触发 LAYER2，由 C 复查 | nodes/surface_scanner.py:53 |
| B | intent=OTHER, confidence=0.0 | 多数组合触发 LAYER2 | nodes/intent_probe.py:63 |
| C | is_violation=False | 放行，宁可漏不放错 | nodes/context_judge.py:69 |
| D | 最小 fallback 摘要 | final_decision 已定，不影响结果 | nodes/evidence_summarizer.py:101 |

---

## 仲裁决策

### pre_filter — 前置分流

| surface_risk | intent | 结果 |
| :--- | :--- | :--- |
| HIGH | 任意 | LAYER2 |
| 任意 | HARASSMENT / SOLICITATION | LAYER2 |
| LOW | NORMAL_SOCIAL / OPINION_EXPRESSION / INFORMATION_SEEKING | PASS |
| 其他组合 | | LAYER2 |

LAYER2 走 C 节点，PASS 直接返回。定义在 `arbitration.py:18-42`。

### deep_judge — 深度仲裁

| is_violation | confidence vs threshold | severity | 结果 |
| :--- | :--- | :--- | :--- |
| false | — | — | PASS |
| true | >= auto_block (默认 0.9) | HIGH / EXTREME | BLOCK |
| true | >= human_review (默认 0.7) | — | HUMAN_REVIEW |
| true | — | HIGH / EXTREME | HUMAN_REVIEW |
| true | 低于以上阈值 | LOW / MEDIUM | PASS |

阈值在 `config.json` 中配置。定义在 `arbitration.py:45-71`。

---

## 基础设施

### 缓存体系

基于 **diskcache**（SQLite），两层层级互相独立：

| 层级 | 缓存 key 构造 | 命中效果 | 代码位置 |
| :--- | :--- | :--- | :--- |
| 请求级 | SHA256(json({text, scene, locale, schema_version})) | 跳过全流程 | cache.py L49-79 |
| 节点级 | SHA256(json({node_name, params, schema_version})) | 跳过该节点 LLM | cache.py L58-94 |

- **写回策略**：请求级在 process() 结束前统一写回，节点级在每个节点执行完后立即写回
- **失效方式**：TTL 过期（默认 86400s）+ `invalidate_by_prefix()` 手动批量删除

### LLM 调用层

所有节点共用同一 `LLMClient.chat()` 方法：

```python
chat(system_prompt, user_message, node_config, json_output=False) → dict
```

定义在 `llm_client.py:37-74`。

特性：

- 节点参数通过 `NodeConfig` 独立控制（thinking/temperature/max_tokens）
- `response_format={"type": "json_object"}` 强制 LLM 输出 JSON
- thinking 模式通过 `extra_body={"thinking": {"type": "enabled"}}` 启用（仅 C 节点）
- JSON 输出无法解析时走 `_try_repair_json()` 修复截断

**JSON 修复策略**（`llm_client.py:77-142`）：

1. 扫描截断处括号栈确定层数
2. 补充值末尾冒号后的空值占位
3. 闭合未完成的字符串
4. 无法修复则返回 None，由调用方触发降级

### 提示词管理

**`prompts.py`** 是所有 AI 节点提示词的定义源，引入 `Prompt` 数据类：

```python
@dataclass(frozen=True)
class Prompt:
    name: str          # 节点名
    version: str       # 版本号，改提示词时递增
    system_prompt: str # 发送给 LLM 的 system message
```

四个实例：

| 变量 | name | version | 消费方 |
| :--- | :--- | :--- | :--- |
| `SURFACE_SCANNER` | surface_scanner | 1.1 | nodes/surface_scanner.py |
| `INTENT_PROBE` | intent_probe | 1.1 | nodes/intent_probe.py |
| `CONTEXT_JUDGE` | context_judge | 2.2 | nodes/context_judge.py |
| `EVIDENCE_SUMMARIZER` | evidence_summarizer | 1.1 | nodes/evidence_summarizer.py |

共享格式指令 `FORMAT_HEADER = "仅输出严格json，禁止任何其他文本。"` 自动拼入每个 Prompt 开头。改提示词只需编辑 `prompts.py`，无需改动节点逻辑代码。

### 参数管理约定

```python
# 每个节点函数内部自行取参
node_config = config.<节点名>    # 如 config.surface_scanner
# node_config 类型: NodeConfig(thinking, temperature, max_tokens)
```

`config.json` 中每个节点有一个同名配置块，与节点函数名软对应（不报错，保持一致即可）。

---

## 配置加载

```python
Config.from_file(path)
  └─ config.py [L81-90]
```

支持 `.json` 和 `.yaml` 两种格式，按后缀决定解析器。

字段解析顺序：文件字段 > 代码默认值。
`api_key` 额外检查 `DEEPSEEK_API_KEY` 环境变量作为备选。

---
