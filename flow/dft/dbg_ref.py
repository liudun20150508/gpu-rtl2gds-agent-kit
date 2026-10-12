#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断: 04 阶段 scan_out 校验和 FAIL 的根因定位 (纯 Python 侧)

对已记录的 yosys 门级仿真 sig, 用修复后的参考机 (03_atpg.py 的 CAPTURE_CTRL)
复算, 并对每条链做 -4..+4 的位偏移搜索:
  ndiff == 0  -> 该偏移下逐位精确一致 (纯相位问题)
  ndiff 小    -> 相位 + 少数残余位差异 (另有建模问题)

背景:
  A) 捕获期 rst_n: load_circuit 把 rst_n/scan_en 排除出 PI, good_sim 对未驱动网
     取 0 -> 复位有效。已修: 03_atpg.py 注入 CAPTURE_CTRL = {rst_n:1, scan_en:0}
  B) 卸载采样相位: 观察 got == exp>>1 (popcount 不变) 的纯移位关系
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SCAN = os.path.join(ROOT, "results/dft/02_scan/tiny_npu_scan.v")
PATS = os.path.join(ROOT, "results/dft/03_atpg/patterns.json")
VER = os.path.join(ROOT, "results/dft/04_verify/verify_results.json")
LIB = os.environ.get("SKY130_LIB") or os.path.expanduser(os.environ.get("ORFS_ROOT", "~/tools/OpenROAD-flow-scripts/flow") + "/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib")

g = {"__file__": os.path.join(HERE, "03_atpg.py"), "__name__": "atpg03"}
exec(compile(open(os.path.join(HERE, "03_atpg.py")).read(), "03_atpg.py", "exec"), g)

lib = g["parse_liberty"](LIB)
cir, order, top_inputs = g["load_circuit"](open(SCAN).read(), lib)

mux = {}
for (ty, out, ins, name) in cir.gates:
    if name.endswith("_scanmux"):
        mux[name[:-len("_scanmux")]] = (ins.get("A0", ""), ins.get("A1", ""))
chains = [[] for _ in range(4)]
for ffname, (a0, a1) in mux.items():
    if a1.startswith("scan_in["):
        chains[int(a1[a1.index("[") + 1:a1.index("]")])].append(ffname)
for c in range(4):
    while True:
        head = chains[c][-1]
        qh = next((pins.get("Q", "").strip() for (n, pins) in cir.dffs if n == head), "")
        nxt = next((f for f, (a0, a1) in mux.items() if a1 == qh), None)
        if nxt is None:
            break
        chains[c].append(nxt)
L = [len(c) for c in chains]
print("chains:", L)

pats = json.load(open(PATS))
all_pi = pats["pi_names"]
sel = pats["random_patterns"][:8]
vr = json.load(open(VER))
gotmap = {k: got for k, exp, got in vr["mismatch_patterns"]}


def sigs_for(bits, extra=None):
    pi = {n: int(b) for n, b in zip(all_pi, bits)}
    if extra:
        pi.update(extra)
    vals = g["good_sim"](cir, order, pi)

    def nv(net):
        r = cir.resolve(net)
        if r[0] == "const":
            return 0 if r[1] in (None, 0) else 1
        if r[0] == "net":
            return vals.get(r[1], 0)
        if r[0] == "alias":
            return nv(r[1])
        return 0

    S2 = {ff: nv(d) for ff, d in cir.pseudo_po.items()}
    out = [0, 0, 0, 0]
    for c in range(4):
        for u in range(1, L[c] + 1):
            out[c] = out[c] * 2 + S2[chains[c][L[c] - u]]
    return out


def bits_of(v, n):
    return bin(v)[2:].zfill(n)


for k in sorted(gotmap):
    bits = sel[k]["bits"]
    got = gotmap[k]
    exp = sigs_for(bits)
    print("=== pattern %d ===" % k)
    for c in range(4):
        gc = bits_of(got[c], L[c])
        best = None
        rows = []
        for off in range(-4, 5):
            if off >= 0:
                cand = bits_of(exp[c] >> off, L[c])
            else:
                cand = bits_of(exp[c] << (-off), L[c])[-L[c]:] if L[c] else ""
            nd = sum(1 for a, b in zip(cand, gc) if a != b)
            rows.append((nd, off))
            if nd == 0:
                best = off
                break
        rows.sort()
        print("  chain%d L=%d  best_ndiff=%d @off=%s   (yosys ones=%d, ref ones=%d)"
              % (c, L[c], rows[0][0], rows[0][1],
                 gc.count("1"), bits_of(exp[c], L[c]).count("1")))
