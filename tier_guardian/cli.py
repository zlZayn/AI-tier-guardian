"""CLI 入口
提供命令行方式进行内容审核。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from tier_guardian.config import Config
from tier_guardian.orchestrator import Orchestrator


def main():
    parser = argparse.ArgumentParser(
        description="三庭二审内容审核引擎 - Tier Guardian",
    )
    parser.add_argument("text", nargs="?", help="要审核的文本内容")
    parser.add_argument("--file", "-f", help="从文件读取文本（每行一条）")
    parser.add_argument("--config", "-c", default=None, help="配置文件路径 (JSON/YAML)")
    parser.add_argument(
        "--scene", "-s", default="comment", help="场景类型 (默认: comment)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--json-output", action="store_true", help="以 JSON 格式输出")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = _load_config(args.config)
    orch = Orchestrator(config)

    try:
        if args.file:
            _process_file(orch, args)
        elif args.text:
            _process_single(orch, args.text, args)
        else:
            _repl_mode(orch, args)
    finally:
        orch.close()


def _load_config(path: str | None) -> Config:
    if path:
        return Config.from_file(path)
    config_path = Path("config.json")
    if config_path.exists():
        return Config.from_file(config_path)
    config_path = Path("config.yaml")
    if config_path.exists():
        return Config.from_file(config_path)
    return Config.defaults()


def _process_single(orch: Orchestrator, text: str, args) -> None:
    ctx = orch.process(text, scene=args.scene)
    _output_result(ctx, args)


def _process_file(orch: Orchestrator, args) -> None:
    path = Path(args.file)
    if not path.exists():
        print(f"文件不存在: {args.file}", file=sys.stderr)
        sys.exit(1)

    lines = path.read_text(encoding="utf-8").strip().split("\n")
    results = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        ctx = orch.process(line, scene=args.scene)
        results.append(ctx)

    if args.json_output:
        print(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2))
    else:
        for i, ctx in enumerate(results):
            print(
                f"[{i + 1}] {ctx.final_decision.value if ctx.final_decision else 'UNKNOWN'}: {ctx.text[:80]}"
            )


def _repl_mode(orch: Orchestrator, args) -> None:
    print("三庭二审审核引擎 - 交互模式 (输入 'quit' 退出)")
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in ("quit", "exit", "q"):
            break
        if not text:
            continue
        ctx = orch.process(text, scene=args.scene)
        _output_result(ctx, args)


def _output_result(ctx, args) -> None:
    if args.json_output:
        print(json.dumps(ctx.to_dict(), ensure_ascii=False, indent=2))
    else:
        decision = ctx.final_decision.value if ctx.final_decision else "UNKNOWN"
        print(f"决策: {decision}")
        if ctx.nodes.surface:
            print(f"  表层风险: {ctx.nodes.surface.surface_risk.value}")
        if ctx.nodes.intent:
            print(
                f"  意图: {ctx.nodes.intent.intent.value} (置信度: {ctx.nodes.intent.confidence:.2f})"
            )
        if ctx.nodes.judge:
            v = ctx.nodes.judge.violation
            print(
                f"  违规判定: {v.is_violation} (类型: {v.type}, 严重度: {v.severity.value if v.severity else 'N/A'}, 置信度: {v.confidence:.2f})"
            )
            if ctx.nodes.judge.reasoning_summary:
                print(f"  推理摘要: {ctx.nodes.judge.reasoning_summary}")
        if ctx.nodes.summary:
            print(f"  一句话摘要: {ctx.nodes.summary.one_liner}")
            print(f"  建议操作: {ctx.nodes.summary.suggested_action}")
        print()


if __name__ == "__main__":
    main()
