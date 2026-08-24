# tier_guardian/ — 规则层

继承根规则，见 [../AGENTS.md](../AGENTS.md)。

tier_guardian/ 特有约束：
- 节点签名统一为 `run_*(client, ..., config)`，改签名必须同步 tests/ 与 [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)
- prompts.py 是提示词唯一定义源，节点逻辑内不得硬编码提示词
- 新模块要公开导出时，同步更新 [README.md](README.md) 文件索引
- 文件职责与改动路由 → 见 [README.md](README.md)