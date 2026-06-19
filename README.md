# Tier Guardian

三庭二审 AI 内容审核引擎。正常内容在浅层快速放行，可疑内容逐层深入，最模糊的边界交给人工。

## 架构

四个 AI 审查员分三层协作，纯程序仲裁决定走向，零额外 Token 消耗。

- **Layer 1** — A 表层扫描 + B 意图探测 **并行**执行，程序根据结果决定放行还是深入
- **Layer 2** — C 语境裁决**串行**执行，结合中文网络文化（反讽、黑话、玩笑语气）深度判定
- **Layer 3** — D 证据摘要**按需**执行，仅在需人工复审时整理材料

各节点细节（thinking 开关、触发条件、输入输出契约）见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 快速开始

```bash
pip install -e .
cp config.example.json config.json
# 编辑 config.json，填入 API key
```

环境变量备选：`export DEEPSEEK_API_KEY="sk-xxx"`

## 使用

**Python：**

```python
from tier_guardian.config import Config
from tier_guardian.orchestrator import Orchestrator

orch = Orchestrator(Config.from_file("config.json"))
ctx = orch.process("用户评论内容", scene="comment", locale="zh-CN")
print(ctx.final_decision.value)  # PASS / BLOCK / HUMAN_REVIEW
orch.close()
```

`ctx.nodes` 可查看各节点详细输出（表层命中、意图分类、违规判定、摘要）。

**命令行：**

```bash
python run_batch.py                          # 内置用例 + 预期比对
python run_batch.py "文本内容"               # 单条审核
python run_batch.py --file texts.txt          # 文件批量（每行一条）
```

## 项目结构

```text
tier_guardian/
├── __init__.py              # 包导出：Config, Orchestrator
├── config.py                # 配置数据类 + 枚举
├── models.py                # 数据模型 + TaskContext
├── prompts.py               # 集中管理所有 AI 节点提示词
├── llm_client.py            # LLM 调用封装（OpenAI SDK）
├── arbitration.py           # 程序仲裁（零 Token）
├── cache.py                 # diskcache（SQLite）跨进程缓存
├── orchestrator.py          # 中央编排（并行调度 + 流程控制）
├── cli.py                   # 命令行入口
└── nodes/
    ├── surface_scanner.py       # A - 表层扫描员
    ├── intent_probe.py          # B - 意图探测员
    ├── context_judge.py         # C - 语境裁决员
    └── evidence_summarizer.py   # D - 证据摘要员
```

## 设计原则

- **AI 只做语义判断，程序做所有仲裁** -- 分流和最终判定由纯 Python 函数完成
- **AI 间互不知晓** -- 每个节点只与中央编排器通信，接收输入、返回 JSON
- **降级安全** -- 任何节点失败降级为安全默认值，不阻断流程
- **渐进深入** -- 大部分正常内容在 Layer1 即放行，仅可疑内容消耗 C 节点

## 测试

```bash
python -m pytest tests/ -q
python -m pytest tests/ --cov=tier_guardian --cov-report=term
```

## License

MIT
