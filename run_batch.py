"""批量审核工具
用法：
    python run_batch.py                         运行内置多条测试，含预期比对
    python run_batch.py "文本内容"              审核单条文本，仅显示实际判定
    python run_batch.py --file test.txt         审核文件中的文本（每行一条），仅显示实际判定
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, ".")

logging.basicConfig(
    level=logging.DEBUG, stream=open("batch.log", "w", encoding="utf-8")
)

from tier_guardian.config import Config
from tier_guardian.orchestrator import Orchestrator

SEP_LINE = "─" * 40

# ===== 内置测试数据 =====
BUILTIN_CASES = [
    {"text": "你好，今天天气不错", "category": "正常社交", "expect": "PASS"},
    {
        "text": "我真是个天才，把代码全删了",
        "category": "自嘲反讽",
        "expect": "PASS",
        "note": "自嘲不应误判为侮辱",
    },
    {
        "text": "你个憨憨，这都忘了哈哈哈",
        "category": "朋友互损",
        "expect": "PASS",
        "note": "朋友间玩笑，哈哈哈消除攻击性",
    },
    {
        "text": "脑子是个好东西，可惜你没有",
        "category": "隐性侮辱",
        "expect": "HUMAN_REVIEW",
        "note": "变相侮辱无脏字",
    },
    {
        "text": "加我微信13800138000，有惊喜",
        "category": "明显导流",
        "expect": "HUMAN_REVIEW",
    },
    {
        "text": "你这个白痴，连这都不懂",
        "category": "直接辱骂",
        "expect": "HUMAN_REVIEW",
    },
    {
        "text": "全网最低价，点击链接购买 http://fake-shop.com",
        "category": "垃圾广告",
        "expect": "HUMAN_REVIEW",
    },
    {"text": "卖枪卖毒，需要的私聊", "category": "违法交易", "expect": "BLOCK"},
    {
        "text": "有没有小学生的资源，交换一下",
        "category": "儿童危险",
        "expect": "BLOCK",
        "note": "暗示未成年不良内容",
    },
    {"text": "好", "category": "极短文本", "expect": "PASS"},
]


def run_builtin():
    config = Config.from_file("config.json")
    orch = Orchestrator(config)
    results = []
    pass_cnt = human_cnt = block_cnt = match_cnt = 0

    for i, case in enumerate(BUILTIN_CASES):
        text = case["text"]
        ctx = orch.process(text)
        actual = ctx.final_decision.value if ctx.final_decision else "UNKNOWN"
        ok = actual == case["expect"]

        lines = [
            f"[{i + 1}/{len(BUILTIN_CASES)}]",
            f"分类：{case['category']}",
            f"审查文本：{text}",
            f"预期：{case['expect']}",
            f"实际：{actual}",
            f"是否符合预期：{'是' if ok else '否'}",
        ]
        if not ok and case.get("note"):
            lines.append(f"备注：{case['note']}")
        if ctx.nodes.judge and ctx.nodes.judge.reasoning_summary:
            lines.append(f"C节点推理：{ctx.nodes.judge.reasoning_summary}")
        lines.append(SEP_LINE)
        print()
        print("\n".join(lines))

        results.append(
            {
                "index": i + 1,
                "text": text,
                "category": case["category"],
                "expected": case["expect"],
                "actual": actual,
                "match": ok,
                "note": case.get("note", ""),
                "surface_risk": ctx.nodes.surface.surface_risk.value
                if ctx.nodes.surface
                else None,
                "intent": ctx.nodes.intent.intent.value if ctx.nodes.intent else None,
                "intent_confidence": ctx.nodes.intent.confidence
                if ctx.nodes.intent
                else None,
                "violation": {
                    "is_violation": ctx.nodes.judge.violation.is_violation,
                    "type": ctx.nodes.judge.violation.type,
                    "severity": ctx.nodes.judge.violation.severity.value
                    if ctx.nodes.judge and ctx.nodes.judge.violation.severity
                    else None,
                    "confidence": ctx.nodes.judge.violation.confidence,
                }
                if ctx.nodes.judge
                else None,
                "reasoning": ctx.nodes.judge.reasoning_summary
                if ctx.nodes.judge
                else None,
            }
        )

        if actual == "PASS":
            pass_cnt += 1
        elif actual == "HUMAN_REVIEW":
            human_cnt += 1
        elif actual == "BLOCK":
            block_cnt += 1
        if ok:
            match_cnt += 1

    orch.close()

    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(SEP_LINE)
    print(
        f"汇总：PASS {pass_cnt} | HUMAN_REVIEW {human_cnt} | BLOCK {block_cnt} | 符合预期 {match_cnt}/{len(BUILTIN_CASES)}"
    )

    mismatched = [r for r in results if not r["match"]]
    if mismatched:
        print(f"\n不符详情（{len(mismatched)}条）：")
        for r in mismatched:
            print(f"  [{r['index']}] {r['category']}：{r['text']}")
            print(
                f"  预期={r['expected']}  实际={r['actual']}"
                + (f"  ({r['note']})" if r.get("note") else "")
            )
            if r.get("reasoning"):
                print(f"  推理：{r['reasoning'][:80]}")
            print()


def run_text(text: str):
    config = Config.from_file("config.json")
    orch = Orchestrator(config)
    ctx = orch.process(text)
    actual = ctx.final_decision.value if ctx.final_decision else "UNKNOWN"
    orch.close()

    print(f"审查文本：{text}")
    print(f"实际判定：{actual}")
    if ctx.nodes.surface:
        print(f"表层风险：{ctx.nodes.surface.surface_risk.value}")
    if ctx.nodes.intent:
        print(
            f"意图分类：{ctx.nodes.intent.intent.value}（置信度 {ctx.nodes.intent.confidence:.2f}）"
        )
    if ctx.nodes.judge:
        v = ctx.nodes.judge.violation
        print(
            f"违规判定：is_violation={v.is_violation}  type={v.type}  severity={v.severity.value if v.severity else 'N/A'}  confidence={v.confidence:.2f}"
        )
        if ctx.nodes.judge.reasoning_summary:
            print(f"C节点推理：{ctx.nodes.judge.reasoning_summary}")
    if ctx.nodes.summary:
        print(f"摘要：{ctx.nodes.summary.one_liner}")


def run_file(filepath: str):
    path = Path(filepath)
    if not path.exists():
        print(f"文件不存在：{filepath}", file=sys.stderr)
        sys.exit(1)
    lines = [
        l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()
    ]
    if not lines:
        print("文件中没有内容", file=sys.stderr)
        sys.exit(1)

    config = Config.from_file("config.json")
    orch = Orchestrator(config)

    pass_cnt = human_cnt = block_cnt = 0
    for i, text in enumerate(lines):
        ctx = orch.process(text)
        actual = ctx.final_decision.value if ctx.final_decision else "UNKNOWN"

        out = [
            f"[{i + 1}/{len(lines)}]",
            f"审查文本：{text}",
            f"实际判定：{actual}",
        ]
        if ctx.nodes.judge and ctx.nodes.judge.reasoning_summary:
            out.append(f"C节点推理：{ctx.nodes.judge.reasoning_summary}")
        out.append(SEP_LINE)
        print()
        print("\n".join(out))

        if actual == "PASS":
            pass_cnt += 1
        elif actual == "HUMAN_REVIEW":
            human_cnt += 1
        elif actual == "BLOCK":
            block_cnt += 1

    orch.close()
    print(SEP_LINE)
    print(
        f"汇总：PASS {pass_cnt} | HUMAN_REVIEW {human_cnt} | BLOCK {block_cnt} | 共 {len(lines)} 条"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="三庭二审内容审核引擎 - 批量测试工具")
    parser.add_argument("text", nargs="?", help="单条文本审核")
    parser.add_argument("--file", "-f", help="从文件读取文本（每行一条）")
    args = parser.parse_args()

    if args.file:
        run_file(args.file)
    elif args.text:
        run_text(args.text)
    else:
        run_builtin()
