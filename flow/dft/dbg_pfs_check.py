#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PFS(并行故障模拟) 正确性交叉验证: 串型故障仿真 vs 位并行 PFS

随机抽 N 个故障, 对每个故障做:
  1) 串型仿真: 注入故障 -> 全电路重算 -> 比较所有观测点(FF 的 D 网)与好机
  2) 取 PFS 对该 pattern 返回的 mask 中对应位
两者必须一致。不一致 -> PFS 引擎有 bug。

用法: python3 dbg_pfs_check.py [nsample]
"""
import os, sys, json, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SCAN = os.path.join(ROOT, "results/dft/02_scan/tiny_npu_scan.v")
LIB = os.environ.get("SKY130_LIB") or os.path.expanduser(os.environ.get("ORFS_ROOT", "~/tools/OpenROAD-flow-scripts/flow") + "/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib")

g = {"__file__": os.path.join(HERE, "03_atpg.py"), "__name__": "a3"}
exec(compile(open(os.path.join(HERE, "03_atpg.py")).read(), "03_atpg.py", "exec"), g)

lib = g["parse_liberty"](LIB)
cir, order, top_inputs = g["load_circuit"](open(SCAN).read(), lib)
faults = g["build_faults"](cir)
nf = len(faults)
ALL = (1 << nf) - 1
print("faults:", nf, "gates:", len(cir.gates), "dffs:", len(cir.dffs))


def sim_with(pi_vals, fault=None):
    """串型仿真, 返回观测点(dict net->val)。fault = (fid,desc,kind,site,v) 或 None"""
    val = dict(g["CAPTURE_CTRL"])
    val.update(pi_vals)
    fkind = fsite = fv = None
    if fault:
        fkind, fsite, fv = fault[2], fault[3], fault[4]
        if fkind == "stem":
            val[fsite] = fv
    for gi in order:
        ty, out, ins, name = cir.gates[gi]
        _, _, expr = lib[ty]
        args = {}
        for p, n in ins.items():
            if fault and fkind == "pin" and fsite == (gi, p):
                args[p] = fv
                continue
            r = cir.resolve(n)
            if r[0] == "const":
                args[p] = 0 if r[1] in (None, 0) else 1
            elif r[0] == "net":
                args[p] = val.get(r[1], 0)
            else:
                args[p] = 0
        v = expr.eval(args)
        if fault and fkind == "out" and fsite == gi:
            v = fv
        val[out] = v
    obs = {}
    for ff, dnet in cir.pseudo_po.items():
        r = cir.resolve(dnet)
        if r[0] == "const":
            obs[ff] = 0 if r[1] in (None, 0) else 1
        elif r[0] == "net":
            obs[ff] = val.get(r[1], 0)
        else:
            obs[ff] = 0
    return obs


nsample = int(sys.argv[1]) if len(sys.argv) > 1 else 300
rng = random.Random(20260831)
all_pi = sorted(cir.pi_net)

# 用与 03 相同种子的前 2 个 pattern
rng2 = random.Random(20260831)
pats = []
for i in range(2):
    pats.append({n: rng2.randint(0, 1) for n in all_pi})

fid2bit = {f[0]: i for i, f in enumerate(faults)}
sample = rng.sample(faults, min(nsample, nf))

bad = 0
for k, pi in enumerate(pats):
    good_obs = sim_with(pi)
    mask = g["pfs"](cir, order, pi, faults, ALL)
    n_pfs = bin(mask).count("1")
    n_ser = 0
    mism = []
    for f in sample:
        obs = sim_with(pi, f)
        det_ser = any(obs[x] != good_obs[x] for x in good_obs)
        det_pfs = bool((mask >> fid2bit[f[0]]) & 1)
        if det_ser:
            n_ser += 1
        if det_ser != det_pfs:
            mism.append((f[0], f[1], f[2], f[4], det_ser, det_pfs))
            bad += 1
    print("pattern %d: PFS 检测 %d/%d (%.1f%%) | 抽样 %d 个故障中串型检测 %d | "
          "串型/PFS 不一致 %d"
          % (k, n_pfs, nf, n_pfs / nf * 100, len(sample), n_ser, len(mism)))
    for m in mism[:8]:
        print("   MISMATCH fid=%d %s kind=%s v=%d  serial=%s pfs=%s" % m)

print("总不一致:", bad)
print("结论:", "PFS 与串型一致 ✅" if bad == 0 else "PFS 存在 bug ❌")
