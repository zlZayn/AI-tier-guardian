# Tier Guardian

三庭二审 AI 内容审核引擎。正常内容在浅层快速放行，可疑内容逐层深入，最模糊的边界交给人工。

## 架构

4 个 AI 节点分两阶段推进，纯程序仲裁决定走向，零额外 Token 消耗。

### Layer 1 -- 并行

A 表层扫描和 B 意图探测同时运行。前置仲裁根据结果决定：大部分正常内容在此直接 PASS，可疑内容进入 Layer 2。

### Layer 2 -- 串行

C 语境裁决结合中文网络文化（反讽、黑话、玩笑语气）深度判定。深度仲裁输出 PASS / BLOCK / HUMAN_REVIEW。

### Layer 3 -- 按需

D 证据摘要仅在 HUMAN_REVIEW 时触发，整理上下文摘要供人工复核，不重新判断。

| 节点 | 做什么 | thinking | 触发条件 |
| ---- | ------ | -------- | -------- |
| A – surface_scanner | 仅匹配已知高风险字面模式，不推理意图 | 关 | 始终 |
| B – intent_probe | 判断沟通意图（正常社交 / 诱导 / 骚扰 / 广告 等） | 关 | 始终 |
| C – context_judge | 结合中文网络文化（反讽、黑话、玩笑）判定真实违规 | 开 | A/B 未直接 PASS |
| D – evidence_summarizer | 整理摘要供人工复核，不重新判断 | 关 | 需人工时 |

A 和 B 并行。C 串行于 LAYER2。D 仅在 HUMAN_REVIEW 时触发。

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

```
tier_guardian/
├── config.py               # 配置数据类 + 枚举
├── models.py               # 数据模型 + TaskContext
├── llm_client.py           # LLM 调用封装（OpenAI SDK）
├── arbitration.py          # 程序仲裁（零 Token）
├── cache.py                # diskcache（SQLite）跨进程缓存
├── orchestrator.py         # 中央编排（并行调度 + 流程控制）
├── cli.py
└── nodes/
    ├── surface_scanner.py      # A
    ├── intent_probe.py         # B
    ├── context_judge.py        # C
    └── evidence_summarizer.py  # D
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
