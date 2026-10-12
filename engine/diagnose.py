# -*- coding: utf-8 -*-
"""诊断与闭环迭代。

路径优先级：LLM（显式启用且可用）→ 规则引擎（默认、离线可用）。
无论走哪条路径，都同时给出**坑库命中**作为可追溯的工程经验。
"""
import json
import os
import re
import subprocess

from .config import llm_call
from .knowledge import get_kb
from .prompts import SYSTEM_EDA, analyze_prompt


def _rule_diagnose(kb, stage, metrics, text):
    hits = kb.match_rules(stage, text)
    pitfalls = kb.match_pitfalls(text)
    if not hits:
        return {
            "diagnosis": f"{stage} 阶段指标未见已知模式，建议人工复查报告",
            "fixes": [],
            "pitfalls": pitfalls,
            "risk": "规则库未覆盖（可启用 LLM 模式扩展诊断）",
        }
    best = hits[0]
    return {
        "diagnosis": f"规则库命中: {best.get('symptom')}",
        "fixes": [{"stage": stage, "action": best["action"],
                   "expected_effect": "按知识库经验值预估",
                   "tool": best.get("tool", ""),
                   "verify": best.get("verify", "")}],
        "pitfalls": pitfalls,
        "risk": "规则库修复，建议人工复核",
    }


def diagnose(cfg, stage, metrics, report_excerpt, use_llm=True, kb=None):
    """诊断入口。"""
    kb = kb or get_kb()
    text = (report_excerpt or "") + " " + json.dumps(metrics, ensure_ascii=False)
    if use_llm and cfg.get("mode") != "offline":
        try:
            resp = llm_call(cfg, SYSTEM_EDA,
                            analyze_prompt(stage, json.dumps(metrics, ensure_ascii=False),
                                           report_excerpt or "", kb.workload_notes()))
            m = re.search(r"\{.*\}", resp, re.S)
            if m:
                diag = json.loads(m.group(0))
                diag.setdefault("pitfalls", kb.match_pitfalls(text))
                return diag
        except Exception as e:  # 网络/解析失败一律回退
            print(f"[engine] LLM 调用失败（{e}），回退规则引擎")
    return _rule_diagnose(kb, stage, metrics, text)


def apply_fix(fix_dir, stage, action):
    """把修复动作写进 fix 目录供人工/脚本应用。

    有意不自动改约束文件 —— 后端约束的改动必须有人复核。
    """
    os.makedirs(fix_dir, exist_ok=True)
    fname = os.path.join(fix_dir, f"{stage}_fix.txt")
    with open(fname, "a", encoding="utf-8") as f:
        f.write(f"## {stage}\n{action}\n\n")
    return fname


def run_flow_step(cmd, cwd=".", timeout=7200):
    """执行一个流程步骤，返回 (returncode, stdout 尾部)。"""
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,
                           text=True, timeout=timeout)
        return p.returncode, "\n".join((p.stdout or "").splitlines()[-40:])
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"


def optimize_loop(cfg, stage, run_cmd, report_files, metric_keys,
                  cwd=".", fix_dir="flow/fixes", max_iter=None, use_llm=True, kb=None):
    """闭环：跑流程 → 解析报告 → 诊断 → 记录修复 → 重跑，直至收敛或达上限。"""
    kb = kb or get_kb()
    max_iter = max_iter or cfg.get("max_iterations", 5)
    history = []
    for it in range(max_iter):
        print(f"\n=== [iter {it + 1}/{max_iter}] {stage} ===")
        rc, log_tail = run_flow_step(run_cmd, cwd)
        metrics, excerpt = {}, log_tail
        for rf in report_files:
            if os.path.exists(rf):
                with open(rf, encoding="utf-8", errors="ignore") as f:
                    excerpt += "\n" + f.read()[-1500:]
        for k in metric_keys:
            mm = re.search(rf"{k}\s*[:=]\s*(-?[\d.]+)", log_tail)
            if mm:
                metrics[k] = float(mm.group(1))
        diag = diagnose(cfg, stage, metrics, excerpt, use_llm=use_llm, kb=kb)
        applied = [apply_fix(fix_dir, f["stage"], f["action"])
                   for f in diag.get("fixes", [])]
        history.append({
            "iteration": it + 1, "stage": stage, "returncode": rc,
            "metrics": metrics, "diagnosis": diag["diagnosis"],
            "fixes_applied": applied, "pitfalls": [p["id"] for p in diag.get("pitfalls", [])],
            "risk": diag.get("risk", ""),
        })
        print(f"[iter {it + 1}] rc={rc} metrics={metrics}")
        print(f"[iter {it + 1}] 诊断: {diag['diagnosis']}")
        if rc == 0 and metrics.get("wns", 0) >= cfg.get("slack_threshold_ps", 0):
            print(f"[iter {it + 1}] 收敛: WNS={metrics.get('wns')}")
            break
        if not diag.get("fixes"):
            print("[engine] 无修复建议，终止迭代")
            break
    return history
