# Tier Guardian

三庭二审 AI 内容审核引擎 -- 基于大语言模型的多层流水线审核系统。

## 核心理念

**AI 只做极窄的语义判断，程序做所有仲裁与执行。**

正常内容在无「思考」的前置层被迅速放行，可疑内容逐层深入，最模糊的边界交给人工。

## 架构

流水线分两层，每层由纯程序仲裁决定走向：

**第一层（并行）**：节点 A（表层扫描）和节点 B（意图探测）同时运行，结果汇总后由前置仲裁裁决。
- 如果判定为 PASS，直接放行，流程结束。
- 否则进入 LAYER2（第二层）。

**第二层（串行）**：节点 C（语境裁决）深度分析，结果由深度仲裁裁决。
- 判定为 PASS 放行，或 BLOCK 自动拦截，流程结束。
- 需要人工复核时进入 HUMAN_REVIEW。

**人工复核层**：节点 D（证据摘要）整理上下文和历史案例，推送给审核台。

| 节点 | 角色 | 思考模式 | 说明 |
|------|------|----------|------|
| A – surface_scanner | 表层扫描员 | 关 | 仅匹配字面高风险模式，忽略语境 |
| B – intent_probe | 意图探测员 | 关 | 仅判断行为意图，不评论是否违规 |
| C – context_judge | 语境裁决员 | 开 | 综合语境、反讽、黑话判断真实违规性 |
| D – evidence_summarizer | 证据摘要员 | 关 | 仅当 HUMAN_REVIEW 时触发，整理信息供人工参考 |

A 和 B 严格并行。C 仅在分流为 LAYER2 时串行调用。D 仅在需人工时调用。

## 判定逻辑

### 前置仲裁（纯程序，零 Token）
- 表层风险为 `high` → LAYER2
- 意图为 `harassment` / `solicitation` → LAYER2
- 表层风险 `low` 且意图为 `normal_social` / `opinion_expression` / `information_seeking` → PASS
- 其他 → LAYER2

### 深度仲裁（纯程序）
- 置信度 ≥ 0.9 且严重度为 high/extreme → BLOCK
- 置信度 ≥ 0.7 或严重度为 high/extreme → HUMAN_REVIEW
- 其他 → PASS

## 快速开始

### 环境要求

- Python ≥ 3.11
- 大语言模型 API（支持 OpenAI 兼容接口）

### 安装

```bash
git clone <repo-url>
cd AI-tier-guardian
pip install -e .
# 或
pip install tier-guardian
```

### 配置

复制示例配置并填入 API 信息：

```bash
cp config.example.json config.json
```

编辑 `config.json`：

```json
{
    "model_name": "deepseek-v4-flash",
    "api_base_url": "https://api.deepseek.com/v1",
    "api_key": "sk-your-api-key-here",
    "surface_scanner": {
        "thinking": false,
        "temperature": 0.0,
        "max_tokens": 150
    },
    "intent_probe": {
        "thinking": false,
        "temperature": 0.0,
        "max_tokens": 120
    },
    "context_judge": {
        "thinking": true,
        "temperature": 0.3,
        "max_tokens": 400
    },
    "evidence_summarizer": {
        "thinking": false,
        "temperature": 0.0,
        "max_tokens": 250
    },
    "auto_block_confidence": 0.9,
    "human_review_confidence": 0.7,
    "schema_version": "v2.3.1",
    "cache_ttl_seconds": 86400,
    "redis_url": "redis://localhost:6379/0",
    "cache_max_size": 10000
}
```

也可通过环境变量配置 API Key：

```bash
export DEEPSEEK_API_KEY="sk-xxx"
```

## 使用方式

### Python API

```python
from tier_guardian.config import Config
from tier_guardian.orchestrator import Orchestrator

config = Config.from_file("config.json")
orch = Orchestrator(config)

ctx = orch.process("用户评论内容", scene="comment", locale="zh-CN")
print(ctx.final_decision.value)  # PASS / BLOCK / HUMAN_REVIEW

# 查看各节点详情
if ctx.nodes.surface:
    print(f"表层风险: {ctx.nodes.surface.surface_risk.value}")
    for p in ctx.nodes.surface.patterns:
        print(f"  命中: [{p.id}] {p.category.value} - {p.fragment}")

if ctx.nodes.intent:
    print(f"意图: {ctx.nodes.intent.intent.value} (置信度 {ctx.nodes.intent.confidence})")

if ctx.nodes.judge:
    v = ctx.nodes.judge.violation
    print(f"违规: {v.is_violation}, 类型: {v.type}, 严重度: {v.severity.value if v.severity else 'N/A'}, 置信度: {v.confidence}")

orch.close()
```

### 命令行批量工具

```bash
# 运行内置 27 条测试，含预期比对
python run_batch.py

# 审核单条文本
python run_batch.py "你好，今天天气不错"

# 审核文件中的文本（每行一条）
python run_batch.py --file texts.txt
```

## 项目结构

```
AI-tier-guardian/
├── tier_guardian/
│   ├── __init__.py
│   ├── config.py                  # 配置系统和枚举定义
│   ├── models.py                  # 数据模型与 TaskContext
│   ├── llm_client.py              # LLM 客户端封装（OpenAI SDK）
│   ├── arbitration.py             # 前置分流与深度仲裁逻辑（纯程序）
│   ├── cache.py                   # 缓存管理（LRU + Redis）
│   ├── orchestrator.py            # 中央编排器（流程控制与并行调度）
│   ├── cli.py                     # 命令行入口
│   └── nodes/
│       ├── __init__.py
│       ├── surface_scanner.py     # 节点 A：表层扫描
│       ├── intent_probe.py        # 节点 B：意图探测
│       ├── context_judge.py       # 节点 C：语境裁决
│       └── evidence_summarizer.py # 节点 D：证据摘要
├── tests/
│   ├── __init__.py
│   ├── test_models.py             # 数据模型与序列化测试
│   ├── test_arbitration.py        # 仲裁逻辑单测
│   ├── test_cache.py              # 缓存系统单测
│   └── test_llm_client.py         # LLM 客户端集成测试
├── docs/
│   └── first_plan                 # 架构设计文档
├── run_batch.py                   # 批量审核工具（三种模式）
├── config.example.json            # 配置模板
├── config.json                    # 本地配置（不提交版本库）
├── pyproject.toml                 # 项目元数据与依赖
└── README.md
```

## 数据流转

整个流程中所有 AI 节点互不知晓，各自只与中央程序通信：从程序接收输入，向程序返回 JSON。程序强制校验 JSON Schema，不符则视为「无响应」走降级策略。

流程用 TaskContext 对象贯穿：原始文本先由 A 和 B 并行处理，产出 surface 和 intent 字段；前置仲裁根据这两个字段决定是 PASS 直接返回，还是进入 LAYER2 让 C 节点产出 judge 字段；深度仲裁决定最终为 PASS / BLOCK / HUMAN_REVIEW；如需人工复核则触发 D 节点产出 summary 字段。

## 缓存机制

- **请求级去重**：相同 `text+scene+locale` 在 TTL 内直接返回历史决策
- **节点级缓存**：每个节点按输入参数独立缓存，最大化复用
- 本地内存 LRU + Redis 持久化（可选）

## 测试

```bash
# 运行全部测试
python -m pytest tests/ -q

# 带覆盖率
python -m pytest tests/ --cov=tier_guardian --cov-report=term
```

## 设计原则

1. AI 铁律：每个 AI 只与中央程序通信，AI 间互不知晓
2. 输出强制：所有 AI 输出必须符合预定义 JSON Schema
3. 降级安全：任何节点失败时降级为安全默认值，不阻断流程
4. 纯程序仲裁：分流与最终判定由程序完成，零 Token 消耗
5. 渐进深入：正常内容在浅层放行，可疑内容逐层深入

## License

MIT
