#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DFT Demo · Stage 04  ATPG 模式门级仿真验证
方法: 从 patterns.json 抽取子集 -> 生成扫描 TB (移位装载+捕获+移出) ->
     yosys sim 门级仿真 (SKY130 liberty 行为模型) -> 与 Python 图模型
     参考机逐位比对 scan_out 校验和 -> 逐模式故障模拟交叉验证。
输入: results/dft/03_atpg/patterns.json + results/dft/02_scan/tiny_npu_scan.v
输出: results/dft/04_verify/  (tb_scan_patterns.v / verify_results.json)
用法: python3 04_pattern_verify.py [--n-rand 64] [--n-podem 64] [--max-cycles N]
"""
import re, json, os, sys, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SCAN = os.path.join(ROOT, "results/dft/02_scan/tiny_npu_scan.v")
PATS = os.path.join(ROOT, "results/dft/03_atpg/patterns.json")
LIB = os.environ.get("SKY130_LIB") or os.path.expanduser(os.environ.get("ORFS_ROOT", "~/tools/OpenROAD-flow-scripts/flow") + "/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib")
OUT  = os.path.join(ROOT, "results/dft/04_verify")
SHIFT = 179
NCAPv = 1          # capture 周期数 (由 main 的 --ncap 覆盖, 供 ref_run 使用)

# ---------- 复用 03 的电路模型 ----------
src = open(os.path.join(HERE, "03_atpg.py")).read()
g = {"__file__": os.path.join(HERE, "03_atpg.py"), "__name__": "atpg03"}
exec(compile(src, "03_atpg.py", "exec"), g)

def build_circuit():
    t = open(SCAN).read()
    lib = g["parse_liberty"](LIB)
    cir, order, top_inputs = g["load_circuit"](t, lib)
    return cir, order, top_inputs

# ---------- 链结构: 从 scanmux A1 连接推导 ----------
def derive_chains(cir):
    """返回 chains[c] = [ffname...] (A1=scan_in[c] 者为链头), 以及 ff->(c,j)"""
    mux = {}       # ffname -> (A0, A1)
    for (ty, out, ins, name) in cir.gates:
        if name.endswith("_scanmux"):
            mux[name[:-len("_scanmux")]] = (ins.get("A0", ""), ins.get("A1", ""))
    q_of = {}
    for (ffname, pins) in cir.dffs:
        q_of[pins.get("Q", "").strip()] = ffname
    chains = [[] for _ in range(4)]
    for ffname, (a0, a1) in mux.items():
        if a1.startswith("scan_in["):
            chains[int(a1[a1.index("[")+1:a1.index("]")])].append(ffname)
    pos = {}
    for c in range(4):
        # 从链头沿 A1 链接走
        while True:
            head = chains[c][-1]
            # 找 A1 == head 的 Q 的后继
            qh = next((pins.get("Q", "").strip() for (n, pins) in cir.dffs if n == head), "")
            nxt = next((f for f, (a0, a1) in mux.items() if a1 == qh), None)
            if nxt is None:
                break
            chains[c].append(nxt)
        for j, f in enumerate(chains[c]):
            pos[f] = (c, j)
    return chains, pos

# ---------- 参考机: 装载序列 / 捕获 / 移出校验和 ----------
def ref_run(pat_bits, cir, order, chains, all_pi, q_index):
    """pat_bits: 全 PI 位串; 返回 (load_mem 行, 期望 sig 列表)

    移位拍数 SH = 最长链长 (随扫描链结构变化: 观测点插入后链变长)。
    """
    SH = max(len(c) for c in chains)
    # 每链装载状态 S[j]
    S = {}
    for c in range(4):
        for j, f in enumerate(chains[c]):
            q = next(pins.get("Q", "").strip() for (n, pins) in cir.dffs if n == f)
            S[(c, j)] = int(pat_bits[q_index[q]])
    # 装载位: 总移位 179 拍, 第 t 拍施加的位落在链位 SHIFT-t (SHIFT-t>=Lc 的位被移出丢弃)
    load_bits = []
    for t in range(1, SH + 1):
        d = 0
        for c in range(4):
            Lc = len(chains[c])
            j = SH - t
            if 0 <= j < Lc:
                d |= (S[(c, j)] << c)
        load_bits.append(d)
    # 捕获: 全 PI 赋值 -> 好机仿真 -> S'[j] = D 网值
    pi = {n: int(b) for n, b in zip(all_pi, pat_bits)}
    # 捕获态: 异步复位反馈迭代求稳态 (与门级 04 前的行为一致), 见 03.capture_state
    _, q_ff, vals = g["capture_state"](cir, order, pi, ncap=NCAPv)
    def nv(net):
        r = cir.resolve(net)
        if r[0] == "const":
            return 0 if r[1] in (None, 0) else 1
        if r[0] == "net":
            return vals.get(r[1], 0)
        if r[0] == "alias":
            return nv(r[1])
        return 0
    S2 = {}
    for (ffname, dnet) in cir.pseudo_po.items():
        S2[ffname] = nv(dnet)
    # 移出校验和: 链 c 第 u 位 = S'[Lc-u] (u=1..Lc); 64 位回绕与 TB reg 一致
    sigs = [0, 0, 0, 0]
    for c in range(4):
        Lc = len(chains[c])
        for u in range(1, Lc + 1):
            f = chains[c][Lc - u]
            sigs[c] = sigs[c] * 2 + S2[f]
    return load_bits, sigs

def main():
    global NCAPv
    argv = sys.argv[1:]
    NCAPv = int(argv[argv.index("--ncap") + 1]) if "--ncap" in argv else 1
    n_rand = int(argv[argv.index("--n-rand") + 1]) if "--n-rand" in argv else 64
    n_podem = int(argv[argv.index("--n-podem") + 1]) if "--n-podem" in argv else 64
    os.makedirs(OUT, exist_ok=True)

    pats = json.load(open(PATS))
    all_pi = pats["pi_names"]
    q_index = {q: all_pi.index(q) for q, isq in pats["pi_is_q"].items() if isq}
    non_q_pis = [n for n, isq in pats["pi_is_q"].items() if not isq]
    print(f"patterns.json: {len(pats['random_patterns'])} random + "
          f"{len(pats['podem_patterns'])} podem; PI={len(all_pi)} "
          f"(Q={len(q_index)}, func={len(non_q_pis)})")

    cir, order, top_inputs = build_circuit()
    chains, pos = derive_chains(cir)
    global SHIFT
    SHIFT = max(len(c) for c in chains)      # 移位拍数 = 最长链 (观测点插入后会变长)
    print("shift cycles (实测链长):", SHIFT)
    print("chains:", [len(c) for c in chains])
    lens_c = [len(c) for c in chains]
    assert len(lens_c) == 4 and max(lens_c) - min(lens_c) <= 1, f"chain length not balanced: {lens_c}"
    assert len(pos) == len(cir.dffs), f"chain coverage {len(pos)} != DFF {len(cir.dffs)}"

    sel = pats["random_patterns"][:n_rand] + pats["podem_patterns"][:n_podem]
    print(f"verify subset: {len(sel)} patterns")

    # ---- 参考机 + TB 数据 ----
    load_lines = []     # 每行一个 hex digit (4 链装载位)
    cap_lines = []      # 每行一个 hex (功能 PI 捕获值)
    ref_sigs = []
    for k, p in enumerate(sel):
        bits = p["bits"]
        load_bits, sigs = ref_run(bits, cir, order, chains, all_pi, q_index)
        load_lines += [format(d, "x") for d in load_bits]
        cap = 0
        for i, n in enumerate(non_q_pis):
            cap |= (int(bits[all_pi.index(n)]) << i)
        cap_lines.append(format(cap, "x"))
        ref_sigs.append(sigs)
    open(os.path.join(OUT, "load_bits.mem"), "w").write("\n".join(load_lines) + "\n")
    open(os.path.join(OUT, "cap_pi.mem"), "w").write("\n".join(cap_lines) + "\n")

    # ---- TB 生成 ----
    n_cap = len(non_q_pis)
    n_pat = len(sel)
    n_total = n_pat * (2 * SHIFT + 1 + NCAPv) + 20   # 每模式: 180 装载 + NCAP 捕获 + 179 移出
    capw = max(1, n_cap)
    # 端口连接: 标量 .p(_w_i); 向量 .p({_w_msb,...,_w_lsb}) (MSB 在前)
    pi_index = {n: i for i, n in enumerate(non_q_pis)}
    t_scan = open(SCAN).read()
    port_decls = []      # (name, msb, lsb) msb=None 为标量
    for d, names in re.findall(r"^\s*(input)\s+(.*?);", t_scan, re.M):
        for raw in names.split(","):
            parts = raw.strip().split()
            if not parts:
                continue
            nm = parts[-1]
            if nm in ("clk", "rst_n", "scan_en", "scan_in"):
                continue
            if len(parts) > 1 and parts[0].startswith("["):
                m = re.match(r"\[(\d+):(\d+)\]", parts[0])
                port_decls.append((nm, int(m.group(1)), int(m.group(2))))
            else:
                port_decls.append((nm, None, None))
    conn = [".clk(clk)", ".rst_n(1'b1)", ".scan_en(scan_en)",
            ".scan_in(scan_in)", ".scan_out(scan_out)"]
    for (nm, msb, lsb) in port_decls:
        if msb is None:
            conn.append(".%s(_w_%d)" % (nm, pi_index[nm]))
        else:
            lo, hi = min(msb, lsb), max(msb, lsb)
            expr = "{" + ", ".join("_w_%d" % pi_index["%s[%d]" % (nm, b)]
                                    for b in range(hi, lo - 1, -1)) + "}"
            conn.append(".%s(%s)" % (nm, expr))
    outports = []
    for d, names in re.findall(r"^\s*(output)\s+(.*?);", t_scan, re.M):
        for raw in names.split(","):
            nm = raw.strip().split()
            nm = nm[-1] if nm else ""
            if nm and nm != "scan_out":
                outports.append(nm)
    for i, p in enumerate(outports):
        conn.append(".%s(_wo_%d)" % (p, i))
    tb = []
    tb.append("module tb_scan_patterns;")
    tb.append("  reg clk = 0;   // 首拍 posedge 先于任何 negedge, 作暖机拍 (装载阶段 = 180 拍吸收)")
    tb.append("  reg scan_en = 1;")
    tb.append("  reg [3:0] scan_in = 0;")
    tb.append("  wire [3:0] scan_out;")
    tb.append("  integer pidx = 0;")
    tb.append("  integer cyc = 0;")
    tb.append("  reg [1:0] state = 0;   // 0=装载 1=捕获 2=移出")
    tb.append("  reg [3:0] load_mem [0:%d];" % (n_pat * SHIFT - 1))
    tb.append("  reg [%d:0] cap_mem [0:%d];" % (capw - 1, n_pat - 1))
    tb.append("  reg [%d:0] cap_pi;" % (capw - 1))
    tb.append("  initial begin")
    tb.append('    $readmemh("load_bits.mem", load_mem);')
    tb.append('    $readmemh("cap_pi.mem", cap_mem);')
    tb.append("  end")
    for i, p in enumerate(non_q_pis):
        tb.append("  wire _w_%d = cap_pi[%d];" % (i, i))
    for i in range(len(outports)):
        tb.append("  wire _wo_%d;" % i)
    tb.append("  top dut (" + ", ".join(conn) + ");")
    tb.append("  always #1 clk = ~clk;")
    tb.append("  always @(posedge clk) begin")
    tb.append("    case (state)")
    tb.append("      0: begin cyc = cyc + 1; if (cyc == %d) begin state = 1; cyc = 0; end end" % (SHIFT + 1))
    tb.append("      1: begin cyc = cyc + 1; if (cyc == %d) begin state = 2; cyc = 0; end end" % NCAPv)
    tb.append("      2: begin cyc = cyc + 1; if (cyc == %d) begin" % SHIFT)
    tb.append("             state = 0; cyc = 0; pidx = pidx + 1;")
    tb.append("             end end")
    tb.append("    endcase")
    tb.append("  end")
    tb.append("  always @(negedge clk) begin")
    tb.append("    case (state)")
    tb.append("      0: begin scan_en = 1;")
    tb.append("           scan_in = (cyc == 0) ? 4'b0 : load_mem[pidx*%d + cyc - 1]; end" % SHIFT)
    tb.append("      1: begin scan_en = 0; cap_pi = cap_mem[pidx]; end")
    tb.append("      2: begin")
    tb.append("        scan_en = 1;")
    tb.append("        scan_in = 0;")
    tb.append('        $display("U %0d %0d %b%b%b%b", pidx, cyc, scan_out[0], scan_out[1], scan_out[2], scan_out[3]);')
    tb.append("      end")
    tb.append("    endcase")
    tb.append("  end")
    tb.append("endmodule")
    open(os.path.join(OUT, "tb_scan_patterns.v"), "w").write("\n".join(tb) + "\n")

    # ---- yosys sim ----
    if not os.path.exists(os.path.join(OUT, "tiny_npu_scan.v")):
        os.symlink(SCAN, os.path.join(OUT, "tiny_npu_scan.v"))
    os.chdir(OUT)
    ys = ("read_verilog tiny_npu_scan.v; read_liberty -ignore_miss_func %s; "
          "read_verilog tb_scan_patterns.v; hierarchy -top tb_scan_patterns -check; proc; "
          "sim -clock clk -n %d" % (LIB, n_total))
    t0 = __import__("time").time()
    r = subprocess.run(["yosys", "-Q", "-p", ys], capture_output=True, text=True,
                       timeout=3600)
    sim_t = __import__("time").time() - t0
    sim_lines = re.findall(r"^U\s+(\d+)\s+(\d+)\s+([01]{4})\s*$", r.stdout, re.M)
    streams = [[[] for _ in range(4)] for _ in range(n_pat)]
    for m in sim_lines:
        pp, cy = int(m[0]), int(m[1])
        if pp >= n_pat:
            continue
        for ch in range(4):
            if cy < len(chains[ch]):
                streams[pp][ch].append(m[2][ch])
    got = {}
    for pp in range(n_pat):
        row = []
        for ch in range(4):
            sigv = 0
            for b in streams[pp][ch]:
                sigv = sigv * 2 + (1 if b == "1" else 0)
            row.append(sigv)
        got[pp] = tuple(row)
    print(f"yosys sim: {sim_t:.1f}s, U 采样行 {len(sim_lines)}, 组装模式 {len(got)}/{n_pat}")

    # ---- 比对 ----
    n_match = n_miss = 0
    mismatch_pat = []
    for k in range(n_pat):
        exp = tuple(ref_sigs[k])
        if k in got and got[k] == exp:
            n_match += 1
        else:
            n_miss += 1
            mismatch_pat.append((k, exp, got.get(k)))
    print(f"scan_out 校验和比对: {n_match}/{n_pat} 一致"
          + ("" if n_miss == 0 else f", 不一致: {mismatch_pat[:5]}"))

    # ---- 逐模式故障模拟交叉验证 ----
    lib = cir.lib
    faults = g["build_faults"](cir)
    nf = len(faults)
    ALL = (1 << nf) - 1
    det_ok = det_bad = 0
    tot_claim = tot_actual = 0
    t1 = __import__("time").time()
    for k, p in enumerate(sel):
        pi = {n: int(b) for n, b in zip(all_pi, p["bits"])}
        mask = g["pfs"](cir, order, pi, faults, ALL, ncap=NCAPv)
        claim = int(p["mask"], 16)
        tot_claim += bin(claim).count("1")
        tot_actual += bin(mask).count("1")
        if mask == claim:
            det_ok += 1
        else:
            det_bad += 1
    fsim_t = __import__("time").time() - t1
    print(f"逐模式 PFS 复算: {det_ok}/{len(sel)} 模式检测集与导出 mask 完全一致"
          f" (不一致 {det_bad}) [{fsim_t:.0f}s]")
    print(f"子集检测: 导出 mask 合计 {tot_claim} 故障, 复算 {tot_actual}")

    results = {
        "design": "tinyNPU scan",
        "method": "yosys 门级仿真 (liberty 行为模型) vs Python 图模型参考机",
        "n_patterns_verified": n_pat,
        "n_random": min(n_rand, len(pats["random_patterns"])),
        "n_podem": min(n_podem, len(pats["podem_patterns"])),
        "shift_cycles": SHIFT,
        "capture_cycles": NCAPv,
        "sim_cycles": n_total,
        "yosys_sim_seconds": round(sim_t, 1),
        "scanout_sig_match": n_match,
        "scanout_sig_total": n_pat,
        "scanout_verify": "PASS" if n_miss == 0 else "FAIL",
        "pattern_faultsim_mask_match": det_ok,
        "pattern_faultsim_total": len(sel),
        "faultsim_verify": "PASS" if det_bad == 0 else "FAIL",
        "subset_claimed_detections": tot_claim,
        "subset_actual_detections": tot_actual,
        "mismatch_patterns": mismatch_pat[:5],
    }
    json.dump(results, open("verify_results.json", "w"), indent=2, ensure_ascii=False)
    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
