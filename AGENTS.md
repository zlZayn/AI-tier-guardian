# Tier Guardian — 维护索引

## 全局规则
- 分层：正常内容浅层放行，可疑逐层深入，模糊交人工，见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 分工：AI 只做语义判断，程序做所有仲裁；改仲裁不改 AI 节点
- 双件分离：AGENTS.md 只写规则，README.md 只写是什么/怎么改
- 决策记录 → [.agents/notes/](.agents/notes/)

## 常用命令
- uv run pytest tests/ -q
- python run_batch.py
- python run_batch.py "文本"

## 验证快照（2026-08-24）
- pytest: 41 passed / 0 failed

## 待办
- [ ] 用真实 API key 跑一次 run_batch.py 全量比对

## 活跃坑
- config.json 含密钥已被 gitignore，别提交
- process() 签名无 locale 参数，场景走 scene（见 README）
- pyproject 未声明 diskcache（cache.py 依赖它），uv 环境缺包，`uv run pytest` 实际回落系统 Python 才通过（见 [.agents/notes/2026-08-24-architecture-to-docs.md](.agents/notes/2026-08-24-architecture-to-docs.md)）

## 文档地图
- 用户入门 → [README.md](README.md)
- 架构设计 → [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 源码手册 → [tier_guardian/README.md](tier_guardian/README.md)
- 测试手册 → [tests/README.md](tests/README.md)