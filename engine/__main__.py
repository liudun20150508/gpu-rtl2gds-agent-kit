# -*- coding: utf-8 -*-
"""engine CLI。

用法：
  python3 -m engine analyze --stage TIMING --report <报告> [--no-llm]
  python3 -m engine optimize --stage TIMING --run "<命令>" --reports a.rpt,b.rpt
  python3 -m engine pitfalls --text "<报错文本>"
  python3 -m engine bind <netlist.v> [out.tcl]
"""
import argparse
import json
import os
import sys

from .config import load_config
from .diagnose import diagnose, optimize_loop
from .knowledge import get_kb
from .parsers import parse_sta_report, parse_yosys_stat, summarize


def _read(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    return ""


def cmd_analyze(args):
    cfg = load_config(args.config)
    if args.stage == "SYN":
        metrics = parse_yosys_stat(args.report)
    elif args.stage == "TIMING":
        metrics = parse_sta_report(args.report)
    else:
        metrics = {}
    excerpt = _read(args.report)
    print(f"指标: {summarize(metrics)}")
    diag = diagnose(cfg, args.stage, metrics, excerpt, use_llm=not args.no_llm)
    print(json.dumps(diag, ensure_ascii=False, indent=2))
    return 0


def cmd_optimize(args):
    cfg = load_config(args.config)
    history = optimize_loop(
        cfg, args.stage, args.run, args.reports.split(","),
        args.metrics.split(",") if args.metrics else [],
        cwd=args.cwd, fix_dir=args.fix_dir,
        max_iter=args.iterations, use_llm=not args.no_llm)
    out = args.json_out or f"history_{args.stage}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"迭代历史已写入 {out}")
    return 0


def cmd_pitfalls(args):
    kb = get_kb()
    text = args.text or _read(args.report)
    hits = kb.match_pitfalls(text)
    if not hits:
        print("坑库无命中")
        return 0
    for p in hits:
        print(f"--- {p['id']} [{p.get('severity', '?')}] {p['title']}")
        print(f"    阶段: {p.get('stage')}")
        print(f"    修法: {' '.join(str(p['fix']).split())}")
        print(f"    验证: {p.get('verify')}")
    return 0


def cmd_bind(args):
    from .netlist_bind import main as bind_main
    return bind_main([args.netlist] + ([args.out] if args.out else []))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="engine", description="RTL2GDS 后端知识规则引擎")
    ap.add_argument("--config", default=None, help="配置文件路径（默认 engine/config.json）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    stages = ["SYN", "APR", "TIMING", "PV", "IREM", "LEC", "VCLP"]

    a = sub.add_parser("analyze", help="单次分析报告")
    a.add_argument("--stage", required=True, choices=stages)
    a.add_argument("--report", required=True)
    a.add_argument("--no-llm", action="store_true")
    a.set_defaults(func=cmd_analyze)

    o = sub.add_parser("optimize", help="闭环迭代优化")
    o.add_argument("--stage", required=True, choices=stages)
    o.add_argument("--run", required=True, help="流程步骤执行命令")
    o.add_argument("--reports", required=True, help="逗号分隔的报告文件")
    o.add_argument("--metrics", default="", help="逗号分隔的指标名")
    o.add_argument("--cwd", default=".")
    o.add_argument("--fix-dir", default="flow/fixes")
    o.add_argument("--iterations", type=int, default=None)
    o.add_argument("--json-out", default=None)
    o.add_argument("--no-llm", action="store_true")
    o.set_defaults(func=cmd_optimize)

    p = sub.add_parser("pitfalls", help="按报错文本检索坑库")
    p.add_argument("--text", default=None)
    p.add_argument("--report", default=None)
    p.set_defaults(func=cmd_pitfalls)

    b = sub.add_parser("bind", help="生成负载特征实例级约束 TCL")
    b.add_argument("netlist")
    b.add_argument("out", nargs="?", default=None)
    b.set_defaults(func=cmd_bind)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
