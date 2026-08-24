# tier_guardian/ — 核心实现手册

- 职责：四节点三层审核引擎的实现，程序仲裁 + LLM 语义判断
- 对外契约：`__init__.py` 导出 `Config`、`Orchestrator`（用法见 [../README.md](../README.md)）

## 文件索引

| 文件 | 职责 | 关键导出 | 被谁依赖 | 改动后必测 |
| :--- | :--- | :--- | :--- | :--- |
| config.py | 枚举 + Config/NodeConfig 数据类 | Config, FinalDecision, SurfaceRisk, IntentLabel | 全包 | tests/test_models.py |
| models.py | TaskContext + 四节点输出模型 | TaskContext, 各节点 Output, Violation | orchestrator, arbitration, nodes | tests/test_models.py |
| prompts.py | 四个 Prompt 对象的唯一定义处 | SURFACE_SCANNER 等四个 Prompt | nodes/* | 无专项测试，人工核对 |
| llm_client.py | OpenAI SDK 包装 + JSON 修复器 | LLMClient, _try_repair_json | orchestrator, nodes | tests/test_llm_client.py |
| cache.py | diskcache 两层缓存 | CacheManager, CacheStats | orchestrator | tests/test_cache.py |
| case_store.py | 相似案例 SQLite 存储 | CaseStore | orchestrator | 无专项测试 |
| arbitration.py | pre_filter + deep_judge 纯程序仲裁 | pre_filter, deep_judge | orchestrator | tests/test_arbitration.py |
| orchestrator.py | process() 全链路编排 | Orchestrator | cli.py, run_batch.py | tests/ + run_batch.py 集成 |
| cli.py | 命令行入口（单条/文件/REPL） | main() | 用户 | 手动跑 cli 命令 |
| nodes/ | A/B/C/D 四个节点函数 | run_surface_scanner 等 | orchestrator | 通过 orchestrator 路径 |

## 变更影响路由

- 改节点提示词 → 只动 prompts.py，版本号递增
- 改仲裁矩阵 → arbitration.py + tests/test_arbitration.py
- 改节点签名 → 同步 [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) 契约表
- 新增/删除模块 → 更新本索引 + 根 [AGENTS.md](../AGENTS.md) 文档地图

- 使用约束与工作偏好 → 见 [AGENTS.md](AGENTS.md)