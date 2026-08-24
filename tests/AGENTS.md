# tests/ — 规则层

继承根规则，见 [../AGENTS.md](../AGENTS.md)。

tests/ 特有约束：
- 每个被测模块对应一个 `test_<模块>.py`，命名对齐
- 测试不依赖真实 LLM/API key（纯单元测试，靠 mocking 或直接测纯函数）
- 新增模块或改契约时，先看 [README.md](README.md) 对应关系再补测试
- 测试命令：`uv run pytest tests/ -q`（见根 [AGENTS.md](../AGENTS.md)）