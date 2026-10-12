# -*- coding: utf-8 -*-
"""知识库加载与检索。

规则数据全部来自仓库根 rules/*.yaml：
  pitfalls.yaml            —— 坑库（症状/根因/修法/验证）
  report_rules.yaml        —— 阶段诊断规则
  workload_knowledge.yaml  —— AI 负载特征 → 物理设计策略 + 实例绑定表

代码不硬编码任何规则，新增知识只改 YAML。
"""
import os

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

RULES_DIR = os.environ.get(
    "RTL2GDS_RULES_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules"))


def _load(name):
    if yaml is None:
        raise RuntimeError("需要 PyYAML：pip install pyyaml")
    path = os.path.join(RULES_DIR, name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"规则文件缺失: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class KnowledgeBase:
    """加载并检索规则库。整个仓库只有这一处读 YAML。"""

    def __init__(self, rules_dir=None):
        global RULES_DIR
        if rules_dir:
            RULES_DIR = rules_dir
        self.pitfalls = _load("pitfalls.yaml") or []
        self.rules = _load("report_rules.yaml") or []
        wl = _load("workload_knowledge.yaml") or {}
        self.workloads = wl.get("workloads", []) if isinstance(wl, dict) else wl
        self._binding = wl.get("binding", {}) if isinstance(wl, dict) else {}

    # ---- 负载特征 ----
    @property
    def workload_entries(self):
        return [w for w in self.workloads if isinstance(w, dict) and "workload" in w]

    @property
    def binding(self):
        """实例级绑定表：{feature: {modules, region, priority, strategy}}"""
        return self._binding

    def workload_notes(self, limit=2):
        """给 LLM 的负载特征提示（每条取前 limit 个动作）。"""
        return "\n".join(
            f"- {w['workload']}: {'; '.join(w['actions'][:limit])}"
            for w in self.workload_entries)

    # ---- 阶段规则 ----
    def match_rules(self, stage, text):
        """按 stage + 症状关键词匹配诊断规则；无命中返回空列表。"""
        low = (text or "").lower()
        hits = []
        for r in self.rules:
            if r.get("stage") != stage:
                continue
            if any(str(s).lower() in low for s in r.get("symptom", [])):
                hits.append(r)
        return hits

    # ---- 坑库 ----
    def match_pitfalls(self, text, limit=5):
        """按 keywords + symptom 匹配坑库，返回按命中数排序的条目。"""
        low = (text or "").lower()
        scored = []
        for p in self.pitfalls:
            hits = sum(1 for k in p.get("keywords", []) if str(k).lower() in low)
            hits += sum(1 for s in p.get("symptom", []) if str(s).lower() in low)
            if hits:
                scored.append((hits, p))
        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored[:limit]]


_CACHE = {}


def get_kb(rules_dir=None):
    """进程内缓存，避免重复读盘。"""
    key = rules_dir or RULES_DIR
    if key not in _CACHE:
        _CACHE[key] = KnowledgeBase(rules_dir)
    return _CACHE[key]
