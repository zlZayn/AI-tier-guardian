# 决策：依赖修正根因 — 移除未用依赖 + dev 迁 dependency-groups（2026-08-28）

已实施。

## 问题

pyproject 声明 redis/cachetools 但代码从未 import（唯一真实依赖递归为 diskcache，cache.py:18）。
同时 dev 依赖放在 `[project.optional-dependencies]`（extras），`uv run` 默认不装 extras。
副作用链：`.venv` 无 diskcache、无 pytest → `uv run pytest` 无声回落系统 Python 的 pytest 9.0.3 + diskcache 才通过。
后果：测试数字看起来正确，但验证环境与 uv.lock 声明的 9.1.1 不一致，换机必裂。

## 决策

- dependencies 移除 redis、cachetools，补 `diskcache>=5.0`（>= 宽松锁）
- dev 从 `[project.optional-dependencies]` 迁移到 `[dependency-groups] dev`（uv 默认同步的组）
- `uv lock` + `uv sync` 重生成；`.venv` 安装 pytest 9.1.1（与 lock 一致）
- AGENTS.md 常用命令恢复 `uv run python run_batch.py`；验证快照标注「项目 venv 内」

## 替代方案（强制）

- 继续 optional-dependencies + 文档提示 `--extra dev`：靠文档提醒，uv run 默认仍不装，易再次暗渡
- 保持系统 Python 兜底：验证数字失真（9.0.3 vs lock 9.1.1），环境不可复现
- optional-dependencies 与 dependency-groups 双声明：两处维护，uv lock 会出现重复解析，易分叉

## 影响

- `uv run pytest tests/ -q` 在项目 venv 内 41 passed / 0 failed（基线不变，环境真实）
- 移除 async-timeout（redis 传递依赖）；uv.lock 由 30 包收敛为 28 包
- 相关变更：725e748（依赖修正）、e867339（快照同步）、0e724e0（uv.lock 源统一清华镜像）