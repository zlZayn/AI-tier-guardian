# 决策：ARCHITECTURE.md 移入 docs/ 并建双件文档（2026-08-24）

状态：生效

## 问题

根目录散落 ARCHITECTURE.md，与 maintenance-flow 技能要求不符：架构文档统一放 `docs/ARCHITECTURE.md`，根目录只留指针；且 tier_guardian/、tests/ 缺 AGENTS.md + README.md 双件，文档与实际代码有出入（README 示例带不存在的 locale 参数、目录树漏 case_store.py）。

## 决策

- `git mv ARCHITECTURE.md docs/ARCHITECTURE.md`，保留 git 历史
- README 链接改为 docs/ARCHITECTURE.md，示例去掉 locale 参数
- 根 AGENTS.md 建仪表盘（≤30 行）；tier_guardian/、tests/ 各建双件
- .agents/notes/ 建决策记录目录
- 顺带修正 ARCHITECTURE 内过时契约（locale 输入、Step 5 similar_cases 来源）

## 替代方案（强制）

- 不移动 ARCHITECTURE：违背统一位置约定，与已有 README/AGENTS 双件体系不一致
- 复制而非 git mv：产生两份来源，后续维护会分叉
- 重建 docs/ 双件而不动根文档：文档与代码矛盾继续存在（locale 参数、case_store 缺失）

## 影响

- 所有 markdown 相对链接以文件所在目录为基准已修正
- 验证快照：`uv run pytest tests/ -q` = 41 passed / 0 failed
- 待办：无真实 API key，run_batch.py 全量比对未跑