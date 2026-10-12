# -*- coding: utf-8 -*-
"""报告解析器：把开源 EDA 工具的报告转成结构化指标。

新增工具时在这里加一个 parse_* 函数即可，其余部分不需要改动。
"""
import os
import re


def _read(path):
    if not path or not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


def parse_yosys_stat(rpt):
    """解析 yosys `stat -liberty` 输出。"""
    m = {}
    text = _read(rpt)
    if not text:
        return m
    mm = re.search(r"Chip area for top module.*?:\s*([\d.]+)", text)
    if mm:
        m["total_area_um2"] = float(mm.group(1))
    mm = re.search(r"of which used for sequential elements:\s*([\d.]+)", text)
    if mm:
        m["seq_area_um2"] = float(mm.group(1))
    areas = re.findall(r"Chip area for module.*?:\s*([\d.]+)", text)
    if areas:
        m["module_count"] = len(areas)
        m["sum_module_area_um2"] = round(sum(float(a) for a in areas), 1)
    return m


def parse_sta_report(rpt):
    """解析 OpenSTA / PrimeTime 时序报告。"""
    m = {"wns": None, "tns": None, "period": None}
    text = _read(rpt)
    if not text:
        return m
    # 工具的报告格式差异很大（PrimeTime / OpenSTA / Tempus），
    # 因此用「指标名 + 任意非数值分隔符 + 数值」的宽松模式。
    for key, pat in (("wns", r"(?:worst negative slack|wns)\D*?(-?[\d.]+)"),
                     ("tns", r"(?:total negative slack|tns)\D*?(-?[\d.]+)"),
                     ("period", r"period\D*?([\d.]+)")):
        mm = re.search(pat, text, re.I)
        if mm:
            m[key] = float(mm.group(1))
    paths = re.findall(r"(?:Startpoint|Endpoint)\s*:\s*(\S+)", text)
    if paths:
        m["endpoints"] = sorted(set(paths))[:10]
    return m


def parse_openroad_log(log, metrics):
    """从 OpenROAD 日志里抽取指定指标名。"""
    out = {}
    text = _read(log)
    if not text:
        return out
    for name in metrics:
        mm = re.search(rf"{name}\s*[:=]\s*(-?[\d.]+)", text)
        if mm:
            out[name] = float(mm.group(1))
    return out


def summarize(metrics):
    """指标 -> 一行摘要。"""
    parts = [f"{k}={v}" for k, v in (metrics or {}).items() if v is not None]
    return ", ".join(parts) if parts else "无指标数据"
