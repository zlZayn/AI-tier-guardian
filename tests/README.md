# tests/ — 测试手册

- 职责：tier_guardian 纯单元测试，不触网、不需要 API key

## 测试 ↔ 被测模块

| 测试文件 | 被测模块 | 覆盖点 |
| :--- | :--- | :--- |
| test_arbitration.py | tier_guardian/arbitration.py | pre_filter / deep_judge 决策矩阵 |
| test_cache.py | tier_guardian/cache.py | CacheManager 哈希与命中逻辑 |
| test_llm_client.py | tier_guardian/llm_client.py | JSON 截断修复器 |
| test_models.py | tier_guardian/models.py | 枚举、PatternHit、TaskContext |

## 特殊坑

- 测试目录被 pyproject `testpaths = ["tests"]` 锁定，新测试文件名必须以 `test_` 开头
- 改节点/仲裁/模型契约 → 同步改对应测试文件，再跑 `uv run pytest tests/ -q`

- 变更影响路由：任一模组改动回查根 [AGENTS.md](../AGENTS.md) 验证快照与待办