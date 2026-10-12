#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查: 模型认定的链尾 FF 是否为驱动 scan_out 的那个 (纯 Python, 不跑 yosys)"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SCAN = os.path.join(ROOT, "results/dft/02_scan/tiny_npu_scan.v")
LIB = os.environ.get("SKY130_LIB") or os.path.expanduser(os.environ.get("ORFS_ROOT", "~/tools/OpenROAD-flow-scripts/flow") + "/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib")

g = {"__file__": os.path.join(HERE, "03_atpg.py"), "__name__": "a3"}
exec(compile(open(os.path.join(HERE, "03_atpg.py")).read(), "03_atpg.py", "exec"), g)

lib = g["parse_liberty"](LIB)
cir, order, ti = g["load_circuit"](open(SCAN).read(), lib)

mux = {}
for (ty, out, ins, name) in cir.gates:
    if name.endswith("_scanmux"):
        mux[name[:-len("_scanmux")]] = (ins.get("A0", ""), ins.get("A1", ""))
chains = [[] for _ in range(4)]
for ff, (a0, a1) in mux.items():
    if a1.startswith("scan_in["):
        chains[int(a1[a1.index("[") + 1:a1.index("]")])].append(ff)
for c in range(4):
    while True:
        h = chains[c][-1]
        qh = next((p.get("Q", "").strip() for (n, p) in cir.dffs if n == h), "")
        nxt = next((f for f, (a0, a1) in mux.items() if a1 == qh), None)
        if nxt is None:
            break
        chains[c].append(nxt)

q2ff = {p.get("Q", "").strip(): n for (n, p) in cir.dffs}
TAPS = ["vec_busy_r", "gelu_done", "gelu_busy_r", "vec_done"]

for c, tap in enumerate(TAPS):
    L = len(chains[c])
    tail = chains[c][-1]
    tq = next((p.get("Q", "").strip() for (n, p) in cir.dffs if n == tail), "")
    ff = q2ff.get(tap)
    pos = chains[c].index(ff) if ff in chains[c] else None
    print("chain%d L=%d  scan_out=%s" % (c, L, tap))
    print("   model tail = %s  Q=%s   -> %s" % (tail, tq, "MATCH" if tq == tap else "MISMATCH"))
    print("   tap FF=%s  在链中 index=%s (距尾部 %s)"
          % (ff, pos, (L - 1 - pos) if pos is not None else "NA"))

    # 头尾确认
    head = chains[c][0]
    ha1 = mux.get(head, ("", ""))[1]
    print("   head=%s  A1=%s" % (head, ha1))
