# -*- coding: utf-8 -*-
"""engine 单元测试。

运行：python3 -m unittest discover -s tests -v   （在仓库根执行）
"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.config import load_config                      # noqa: E402
from engine.diagnose import diagnose, apply_fix            # noqa: E402
from engine.knowledge import KnowledgeBase, get_kb         # noqa: E402
from engine.netlist_bind import bind, gen_tcl, parse_modules  # noqa: E402
from engine.parsers import parse_sta_report, parse_yosys_stat, summarize  # noqa: E402

RULES = os.path.join(ROOT, "rules")
EXAMPLE = os.path.join(ROOT, "examples", "reports", "sta_wns_fail.rpt")


class TestKnowledge(unittest.TestCase):
    def test_loads_three_rule_files(self):
        kb = KnowledgeBase(RULES)
        self.assertGreaterEqual(len(kb.pitfalls), 10)
        self.assertGreaterEqual(len(kb.rules), 8)
        self.assertEqual(len(kb.workload_entries), 5)
        self.assertEqual(len(kb.binding), 4)

    def test_rule_match_by_stage_and_symptom(self):
        kb = KnowledgeBase(RULES)
        hits = kb.match_rules("TIMING", "worst slack is negative, wns violated")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["stage"], "TIMING")

    def test_rule_no_match_for_other_stage(self):
        kb = KnowledgeBase(RULES)
        self.assertEqual(kb.match_rules("TIMING", "isolation cell missing"), [])

    def test_pitfall_match_by_keyword(self):
        kb = KnowledgeBase(RULES)
        hits = kb.match_pitfalls("read_spef failed with STA-1670 syntax error")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["id"], "PIT-005")

    def test_pitfall_match_segfault(self):
        kb = KnowledgeBase(RULES)
        hits = kb.match_pitfalls("Signal 11 received in makePortFuncs unknown port IQ")
        self.assertEqual(hits[0]["id"], "PIT-001")


class TestParsers(unittest.TestCase):
    def test_parse_sta_example(self):
        m = parse_sta_report(EXAMPLE)
        self.assertAlmostEqual(m["wns"], -0.35, places=2)
        self.assertAlmostEqual(m["tns"], -12.480, places=2)
        self.assertTrue(m.get("endpoints"))

    def test_parse_missing_file_is_safe(self):
        self.assertEqual(parse_yosys_stat("/nonexistent/x.rpt"), {})
        self.assertIsNone(parse_sta_report("/nonexistent/x.rpt")["wns"])

    def test_summarize(self):
        self.assertIn("wns=", summarize({"wns": -0.35, "skip": None}))


class TestDiagnose(unittest.TestCase):
    def test_offline_rule_path(self):
        cfg = load_config()          # 默认 offline
        kb = KnowledgeBase(RULES)
        diag = diagnose(cfg, "TIMING", {"wns": -0.35},
                        open(EXAMPLE, encoding="utf-8").read(), use_llm=False, kb=kb)
        self.assertIn("diagnosis", diag)
        self.assertTrue(diag["fixes"])
        self.assertEqual(diag["fixes"][0]["stage"], "TIMING")

    def test_unknown_stage_yields_no_fix(self):
        cfg = load_config()
        kb = KnowledgeBase(RULES)
        diag = diagnose(cfg, "APR", {"x": 1}, "完全未知的报错文本", use_llm=False, kb=kb)
        self.assertEqual(diag["fixes"], [])

    def test_apply_fix_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = apply_fix(d, "TIMING", "降低目标频率并重跑")
            self.assertTrue(os.path.exists(path))
            self.assertIn("TIMING", open(path, encoding="utf-8").read())


class TestNetlistBind(unittest.TestCase):
    NETLIST = """module top(a, y);
  input a; output y;
  cache_data u_cd (.a(a));
  cache_tags u_ct (.a(a));
  fpu_unit   u_fp (.a(a));
  wallace_mul u_wm (.a(a));
  mem_xbar   u_xb (.a(a));
  axi        u_axi (.a(a));
  unrelated_cell u_x (.a(a));
endmodule
"""

    def _write(self):
        f = tempfile.NamedTemporaryFile("w", suffix=".v", delete=False)
        f.write(self.NETLIST)
        f.close()
        return f.name

    def test_parse_and_bind(self):
        p = self._write()
        try:
            self.assertIn("fpu_unit", parse_modules(p))
            b = bind(p, KnowledgeBase(RULES))
            feats = {x["feature"] for x in b}
            self.assertEqual(feats, {"kv_cache", "qkv_gemm", "moe_noc", "tp_hbm"})
            tcl = gen_tcl(b, top="top")
            self.assertIn("group_path -name qkv_datapath", tcl)
            self.assertIn("cache_data", tcl)
        finally:
            os.unlink(p)

    def test_empty_netlist_no_binding(self):
        with tempfile.NamedTemporaryFile("w", suffix=".v", delete=False) as f:
            f.write("module top(); endmodule\n")
            p = f.name
        try:
            self.assertEqual(bind(p, KnowledgeBase(RULES)), [])
        finally:
            os.unlink(p)


class TestConfig(unittest.TestCase):
    def test_defaults_offline(self):
        cfg = load_config("/nonexistent/config.json")
        self.assertEqual(cfg["mode"], "offline")
        self.assertEqual(cfg["max_iterations"], 5)
        self.assertEqual(cfg["ollama"]["model"], "qwen2.5-coder:14b")


if __name__ == "__main__":
    unittest.main(verbosity=2)
