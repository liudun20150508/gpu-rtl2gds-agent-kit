#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三方案指标提取: base / tcu(vortex_llm) / ai(vortex_llm_ai) -> markdown 对比表
用法: python3 flow/extract_metrics.py > report/三方案对比_自动生成.md
"""
import json, os, re, sys

FLOW = os.path.expanduser(os.environ.get("ORFS_ROOT", "~/tools/OpenROAD-flow-scripts/flow"))
DESIGNS = {"基线版(base,TCU关)": "vortex",
           "+TCU版(vortex_llm)": "vortex_llm",
           "AI负载版(vortex_llm_ai)": "vortex_llm_ai"}
EXTRA = {
    "vortex":    {"sta": "WNS +1.13ns (基线实测, 见报告 §5)", "die": "11.41 mm²", "lvs": "237 种单元类型器件级 100% 匹配", "drc": "23 违规 (li.5 单元内部可豁免)"},
    "vortex_llm": {"sta": "WNS +2.29ns / TNS 0.00 / hold +0.02ns (OpenSTA RCX 签核)", "ir": "VDD 0.275mV / VSS 0.316mV"},
    "vortex_llm_ai": {"sta": "见 /tmp/sta_signoff_ai.log", "ir": "见 reports/.../VDD.rpt"},
}

def load_metrics(design):
    m = {}
    for f in [f"{FLOW}/reports/sky130hd/{design}/base/6_final_metrics.json",
              f"{FLOW}/reports/sky130hd/{design}/base/metrics.json"]:
        if os.path.exists(f):
            m.update(json.load(open(f)))
    return m

def stage_elapsed(design):
    """从 logs 汇总各阶段耗时 (json 无则跳过)"""
    d = f"{FLOW}/logs/sky130hd/{design}/base"
    out = {}
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.endswith(".json") and f.startswith(("1_", "2_", "3_", "4_", "5_", "6_")):
                try:
                    j = json.load(open(f"{d}/{f}"))
                    if "elapsed" in str(j).lower() or f == "6_report.json":
                        pass
                except Exception:
                    pass
    return out

def cell_count(design):
    """从 6_final.v 数实例 (顶层统计)"""
    p = f"{FLOW}/results/sky130hd/{design}/base/6_final.v"
    if not os.path.exists(p):
        return "N/A"
    txt = open(p, errors="ignore").read()
    # sky130 cell 实例: <cell> <inst> (
    cells = re.findall(r"^\s*(sky130_fd_sc_hd__\w+)\s+\w+\s*\(", txt, re.M)
    from collections import Counter
    return sum(Counter(cells).values())

def main():
    print("| 指标 | 基线版 (TCU关) | +TCU版 | AI负载版 |")
    print("|------|---------------|--------|---------|")
    rows = {}
    for label, d in DESIGNS.items():
        m = load_metrics(d)
        rows[label] = {
            "cells": cell_count(d),
            "wirelength": next((v for k, v in m.items() if "wirelength" in k.lower() and "final" in k.lower()), None),
            "wns": None, "tns": None,
        }
    for label, d in DESIGNS.items():
        e = EXTRA.get(d, {})
        rows[label]["sta"] = e.get("sta")
        rows[label]["ir"] = e.get("ir")
        rows[label]["drc"] = e.get("drc")
        rows[label]["lvs"] = e.get("lvs")
    keys = ["cells", "wirelength", "sta", "ir", "drc", "lvs"]
    for k in keys:
        vals = [str(rows.get(l, {}).get(k, "-")) for l in DESIGNS]
        print(f"| {k} | " + " | ".join(vals) + " |")

if __name__ == "__main__":
    main()
