#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DFT Demo · Stage 02  SCAN 串链 (mux-D scan insertion)
定位: DFT · SCAN 串链
方法: SKY130 HD lib 无专用扫描触发器 -> 标准 mux-D scan:
     D <- SE ? SI : D (复用 sky130_fd_sc_hd__mux2_1), 713 FF 均衡串 4 链。
输出: results/dft/02_scan/  (tiny_npu_scan.v / scan_stats.json / tb_scan_shift.v)
"""
import re, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(ROOT, "results/dft/01_synth/tiny_npu_netlist.v")
OUT = os.path.join(ROOT, "results/dft/02_scan")
NCHAIN = 4
NCYC = 460          # TB 移位周期数 (> 2*max_chain)
MUX_AREA, TOTAL_AREA = 11.2608, 28642.4704
FF_AREA = 25.024          # sky130_fd_sc_hd__dfrtp_1 (测试点 FF)
TP_MAX = 48               # 观测点上限
TP_MIN_FANOUT = 6         # 只挑高扇出网

os.makedirs(OUT, exist_ok=True)
txt = open(SRC).read()

# ---------------- parse ----------------
m = re.search(r"module\s+(\w+)\s*\((.*?)\)\s*;", txt, re.S)
modname, portlist = m.group(1), m.group(2)
ports = [p.strip() for p in portlist.replace("\n", " ").split(",") if p.strip()]

decl = {}   # port -> direction
for d, names in re.findall(r"^\s*(input|output)\s+(.*?);", txt, re.M):
    for raw in names.split(","):
        nm = raw.strip().split()
        nm = nm[-1] if nm else ""
        if nm:
            decl[nm] = d
inports = [p for p in ports if decl.get(p) == "input"]
outports = [p for p in ports if decl.get(p) == "output"]

insts = []
for mm in re.finditer(r"^\s{1,2}(sky130_fd_sc_hd__\w+)\s+(\S+)\s*\((.*?)^\s*\);", txt, re.M | re.S):
    pins = dict(re.findall(r"\.(\w+)\((.*?)\)", mm.group(3), re.S))
    # 注意: 不 strip —— 转义标识符 `\u_regs.aw_latched ` 的尾随空格
    # 是 Verilog 语法的一部分 (转义名以空白结尾), 去掉会改变网名
    insts.append(dict(type=mm.group(1), name=mm.group(2), pins=pins))

dffs = [i for i in insts if i["type"] == "sky130_fd_sc_hd__dfrtp_1"]
dffs.sort(key=lambda i: i["name"])
assert len(dffs) == 713, f"DFF count mismatch: {len(dffs)}"

# ---------------- 测试点插入 (观测点 / test point insertion) ----------------
# 覆盖率瓶颈: 组合逻辑内部节点不可观测 —— 既不是任何 FF 的 D、也不是顶层输出的
# 高扇出内部网, 其 stuck-at 故障传不到伪 PO。标准做法是插观测点: 给这类网各加一个
# test-only DFF (Q 不参与功能逻辑) 采样该网, 并把该 DFF 串入扫描链 —— 功能模式下
# 它跟随被观测网, 测试模式下随链移出, 于是这批网变成可观测。
fanout = {}
for ins in insts:
    for p, n in ins["pins"].items():
        k = n.strip()
        if k:
            fanout[k] = fanout.get(k, 0) + 1
observed = set(o.strip() for o in outports)
for d in dffs:
    observed.add(d["pins"].get("D", "").strip())
pi_set = set(inports)
cand = [(c, n) for n, c in fanout.items()
        if c >= TP_MIN_FANOUT and n not in observed and n not in pi_set
        and not n.startswith("{") and "'" not in n and not n[0].isdigit()]
cand.sort(key=lambda x: (-x[0], x[1]))
tp_nets = [n for _c, n in cand[:TP_MAX]]

def vname(net):
    r"""Verilog 转义标识符(\ 开头)必须以空白结束, 否则 .A0(\\u_regs.x), 会被解析成
    标识符 'u_regs.x),' -> 语法错误。统计时 strip 过, 这里补回尾随空格。"""
    return net + " " if net.startswith("\\") else net

for i, net in enumerate(tp_nets):
    dffs.append(dict(type="sky130_fd_sc_hd__dfrtp_1", name=f"tp_obs_{i}",
                     pins={"CLK": "clk", "D": vname(net), "Q": f"tp_q_{i}",
                           "RESET_B": "rst_n"}))
print(f"test points: {len(tp_nets)} 观测点 (候选 {len(cand)}, 阈值 fanout>={TP_MIN_FANOUT}; "
      f"最高扇出 {cand[0][0] if cand else 0})")

# 测试模式复位门控: RESET_B != rst_n 的 DFF, 移位期间强制复位无效
# (扫描链上的寄存器会翻转内部复位逻辑, 如 isobufsrc: X = A & !SLEEP,
#  SLEEP=reg_ctrl[1] 本身在链上 -> 移位时复位每拍误触发, 必须门控)
reset_gate = {}     # name -> (原复位网, 门控后网)
reset_muxes = []    # (inst, type, pins)
for d in dffs:
    rb = d["pins"].get("RESET_B", "")
    if rb and rb.strip() != "rst_n":
        g = d["name"] + "_rbg"
        reset_gate[d["name"]] = (rb, g)
        reset_muxes.append((d["name"] + "_rbgmux", "sky130_fd_sc_hd__mux2_1",
                            {"A0": rb, "A1": "1'b1", "S": "scan_en", "X": g}))
print(f"reset gating: {len(reset_gate)} DFF (RESET_B != rst_n)")

# capture 期间复位网络去耦 (reset de-coupling):
# scan_en=1 时复位被门控没问题; 但 scan_en=0 (capture) 时 rbgmux 取 A0=内部复位网,
# 而该网由链上寄存器 (如 reg_ctrl -> isobufsrc) 驱动, 装载值会让它在 capture 沿
# 翻转到"复位有效", 与时钟沿同拍 -> 复位释放/捕获竞争, 参考机与门级事件仿真不一致。
# 修法: capture 期间把内部复位网强制为释放态 (高), 只在移位期沿用原网。
rst_nets = []
for (rb, _g) in reset_gate.values():
    r = rb.strip()
    if r and r not in rst_nets:
        rst_nets.append(r)
rst_cap = {r: f"rst_cap_{i}" for i, r in enumerate(rst_nets)}
reset_deco_muxes = [(f"rst_capmux_{i}", "sky130_fd_sc_hd__mux2_1",
                     {"A0": "1'b1", "A1": r, "S": "scan_en", "X": rst_cap[r]})
                    for i, r in enumerate(rst_nets)]
# rbgmux 的 A0 改接去耦后的网
for im in reset_muxes:
    _n, _t, pins = im
    pins["A0"] = rst_cap[pins["A0"].strip()]
print(f"reset de-coupling: {len(rst_nets)} 内部复位网{(' (' + ','.join(rst_nets) + ')') if len(rst_nets) <= 4 else ''}")

# ---------------- mux-D 替换 + 串链 ----------------
chain_members = [[] for _ in range(NCHAIN)]
new_mux = []
dff_patch = {}
for k, d in enumerate(dffs):
    c = k % NCHAIN
    j = len(chain_members[c])
    chain_members[c].append(d["name"])
    si = f"scan_in[{c}]" if j == 0 else dffs[k - NCHAIN]["pins"]["Q"]
    new_mux.append((f"{d['name']}_scanmux", "sky130_fd_sc_hd__mux2_1",
                    {"A0": d["pins"]["D"], "A1": si, "S": "scan_en",
                     "X": f"scan_d_{c}_{j}"}))
    dff_patch[d["name"]] = f"scan_d_{c}_{j}"

# ---------------- 发射网表 (外科手术式修改, 保留全部 assign/声明) ----------------
# 1) 仅替换 DFF 实例的 .D 连接 (其余文本逐字节保留)
def repl_dff(m):
    name = m.group(2)
    if name in dff_patch or name in reset_gate:
        body = m.group(3)
        if name in dff_patch:
            dm = re.search(r"\.D\(([^)]*)\)", body)
            if dm:
                body = body[:dm.start(1)] + dff_patch[name] + body[dm.end(1):]
        if name in reset_gate:
            rb_old, rb_new = reset_gate[name]
            rm = re.search(r"\.RESET_B\(([^)]*)\)", body)
            if rm:
                body = body[:rm.start(1)] + rb_new + body[rm.end(1):]
        return f"{m.group(1)}{body}"   # group(1) 已含缩进/celltype/instname/'('
    return m.group(0)

newtxt = re.sub(r"(^\s{1,2}sky130_fd_sc_hd__\w+\s+(\S+)\s*\()(.*?)(?=^\s*\);)", repl_dff, txt, flags=re.M | re.S)

# 2) 模块头加 scan 端口
header = f"module {modname}({portlist.strip()}, scan_in, scan_out, scan_en);"
newtxt = re.sub(r"module\s+\w+\s*\(.*?\)\s*;", header, newtxt, count=1, flags=re.S)

# 3) 声明区插入 scan 端口 + 内部 wire
wire_decls = []
for c in range(NCHAIN):
    for j in range(len(chain_members[c])):
        wire_decls.append(f"  wire scan_d_{c}_{j};\n")
for (rb, g) in reset_gate.values():
    wire_decls.append(f"  wire {g};\n")
for r in rst_nets:
    wire_decls.append(f"  wire {rst_cap[r]};\n")
for i in range(len(tp_nets)):
    wire_decls.append(f"  wire tp_q_{i};\n")
pos = re.search(r"^\s*(?:input|output)\s", newtxt, re.M).start()
newtxt = newtxt[:pos] + ("  input [3:0] scan_in;\n  output [3:0] scan_out;\n"
                         "  input scan_en;\n" + "".join(wire_decls)) + newtxt[pos:]

# 4) endmodule 前追加 713 个 scan mux + scan_out 驱动
mux_txt = "\n".join(
    "  %s %s (\n%s\n  );" % (ctype, iname,
                              ",\n".join(f"    .{p}({n})" for p, n in pins.items()))
    for iname, ctype, pins in new_mux + reset_muxes + reset_deco_muxes)
tp_inst_txt = "\n".join(
    "  sky130_fd_sc_hd__dfrtp_1 tp_obs_%d (\n    .CLK(clk),\n    .D(%s),\n    .Q(tp_q_%d),\n    .RESET_B(rst_n)\n  );"
    % (i, dff_patch[f"tp_obs_{i}"], i) for i in range(len(tp_nets)))
so_txt = "".join(f"  assign scan_out[{c}] = {dffs[c + NCHAIN * (len(chain_members[c]) - 1)]['pins']['Q']};\n"
                 for c in range(NCHAIN))
endmod = re.search(r"^\s*endmodule", newtxt, re.M).start()
newtxt = newtxt[:endmod] + mux_txt + "\n" + tp_inst_txt + "\n" + so_txt + newtxt[endmod:]
open(os.path.join(OUT, "tiny_npu_scan.v"), "w").write(newtxt)

# ---------------- stats ----------------
lens = [len(cm) for cm in chain_members]
stats = {
    "method": "mux-D scan (SKY130 lib 无专用 SDFF, 复用 mux2_1)",
    "n_dff": len(dffs), "n_dff_original": 713, "n_chain": NCHAIN, "chain_lengths": lens,
    "max_chain": max(lens), "min_chain": min(lens),
    "n_mux_added": len(new_mux),
    "n_reset_gated": len(reset_gate),
    "n_reset_deco_mux": len(reset_deco_muxes),
    "reset_deco_note": "capture 期间内部复位网强制释放 (scan_en=0 -> 1), 消除复位释放与时钟沿的竞争",
    "reset_gate_note": "异步复位测试门控: RESET_B!=rst_n 的 DFF 在 scan_en 期间复位无效 (防止链上寄存器翻转内部复位逻辑)",
    "n_test_points": len(tp_nets),
    "test_point_note": "观测点: 采样既非 FF-D 也非顶层输出的高扇出内部网 (test-only DFF, 串入扫描链)",
    "area_overhead_um2": round((len(new_mux) + len(reset_muxes) + len(reset_deco_muxes)) * MUX_AREA
                               + len(tp_nets) * (MUX_AREA + FF_AREA), 2),
    "total_area_um2": TOTAL_AREA,
    "area_overhead_pct": round(((len(new_mux) + len(reset_muxes) + len(reset_deco_muxes)) * MUX_AREA
                                + len(tp_nets) * (MUX_AREA + FF_AREA)) / TOTAL_AREA * 100, 2),
    "n_ports_added": 9, "shift_cycles": max(lens),
}
json.dump(stats, open(os.path.join(OUT, "scan_stats.json"), "w"), indent=2, ensure_ascii=False)

# ---------------- 链完整性 TB (yosys sim, 独立参考移位模型自检) ----------------
def seq(c):
    """4 条链各自独立的移位序列 (确定性)"""
    if c == 0:
        s, out = 0x5A5A, []
        for _ in range(NCYC):
            out.append(s & 1)
            s = ((s >> 1) | (((s ^ (s >> 2)) & 1) << 14))
        return out
    if c == 1:
        return [t & 1 for t in range(NCYC)]
    if c == 2:
        return [int(b) for b in "10100101"] * (NCYC // 8 + 1)
    s, out = 0x39, []
    for _ in range(NCYC):
        out.append(s & 1)
        s = ((s >> 1) | (((s ^ (s >> 1)) & 1) << 6))
    return out

seql = [seq(c)[:NCYC] for c in range(NCHAIN)]
tb = ["module tb_scan_shift;", "  reg clk = 0;", "  reg scan_en = 1;",
      "  reg [3:0] scan_in = 0;", "  wire [3:0] scan_out;",
      "  integer t = 0;", "  integer tchk = 0;", "  integer err = 0;"]
for c in range(NCHAIN):
    tb.append("  reg [%d:0] seq%d = %d'b%s;" % (
        NCYC-1, c, NCYC, "".join(str(b) for b in reversed(seql[c]))))
conn = [".clk(clk)", ".rst_n(1'b1)", ".scan_en(scan_en)",
        ".scan_in(scan_in)", ".scan_out(scan_out)"]
conn += [f".{p}(_w_{i})" for i, p in enumerate(outports)]
conn += [f".{p}(1'b0)" for p in inports if p not in ("clk", "rst_n")]
for i in range(len(outports)):
    tb.append(f"  wire _w_{i};")
tb.append("  top dut (" + ", ".join(conn) + ");")
tb.append("  always #1 clk = ~clk;")
tb.append("  // 激励: negedge 施加 seq[t] (下一 posedge 捕获), 自增计数器")
tb.append("  always @(negedge clk) begin")
tb.append("    if (t < %d) begin" % NCYC)
for c in range(NCHAIN):
    tb.append("      scan_in[%d] = seq%d[t];" % (c, c))
tb.append("      t = t + 1;")
tb.append("    end")
tb.append("  end")
tb.append("  // 独立参考模型: 激励在 negedge 施加 -> 下一周期捕获;")
tb.append("  // yosys sim 在周期边界先执行 always 块再执行 FF 捕获,")
tb.append("  // 故 tchk=N 时 scan_out 为 N-1 周期捕获值 = seq[N-(L+2)]")
tb.append("  always @(negedge clk) begin")
tb.append("    tchk = tchk + 1;")
for c in range(NCHAIN):
    L = lens[c]
    tb.append("    if (tchk >= %d && tchk <= %d && scan_out[%d] !== seq%d[tchk-%d]) begin" % (L+2, NCYC+2, c, c, L+2))
    tb.append('      $display("FAIL chain%d tchk=%%0d exp=%%0b got=%%0b", %d, tchk, seq%d[tchk-%d], scan_out[%d]);' % (c, c, c, L+2, c))
    tb.append("      err = err + 1;")
    tb.append("    end")
tb.append("  end")
tb.append("  initial begin")
tb.append("    #%d;" % (2*NCYC + 40))
tb.append('    if (err == 0) $display("SCAN_CHAIN_SHIFT_ALL_PASS");')
tb.append('    else $display("SCAN_CHAIN_SHIFT_FAIL err=%0d", err);')
tb.append("  end")
tb.append("endmodule")

open(os.path.join(OUT, "tb_scan_shift.v"), "w").write("\n".join(tb) + "\n")

print(json.dumps(stats, indent=2, ensure_ascii=False))
print("in=%d out=%d dff=%d" % (len(inports), len(outports), len(dffs)))

# ---------------- 链完整性验证: yosys sim + VCD + Python 独立比对 ----------------
import subprocess, shlex
LIB = os.environ.get("SKY130_LIB") or os.path.expanduser(os.environ.get("ORFS_ROOT", "~/tools/OpenROAD-flow-scripts/flow") + "/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib")
os.chdir(OUT)
ys = ("read_verilog tiny_npu_scan.v; read_liberty -ignore_miss_func %s; "
      "read_verilog tb_scan_shift.v; hierarchy -top tb_scan_shift -check; proc; "
      "sim -clock clk -n 466 -vcd chain_sim.vcd" % LIB)
r = subprocess.run(["yosys", "-Q", "-p", ys], capture_output=True, text=True)
vcd_path = os.path.join(OUT, "chain_sim.vcd")
assert os.path.exists(vcd_path), "VCD not generated: " + r.stderr[-500:]

# ---- VCD 解析: $scope 跟踪 + $var idmap + 事件回放 ----
vcd = open(vcd_path).read()
scope = []
idmap = {}          # id -> (fullname, width)
for m in re.finditer(r"\$scope\s+\w+\s+([^\s]+)", vcd):
    scope = [m.group(1)]
    break
for m in re.finditer(r"\$scope\s+\w+\s+([^\s]+)", vcd):
    pass
scopes = re.findall(r"\$scope\s+\w+\s+(\S+)\s+\$end", vcd)
# 顺序解析: 跟踪 scope 进出
cur_scope = []
scope_stack = []
pos = 0
for m in re.finditer(r"(\$scope\s+\w+\s+(\S+)\s+\$end|\$upscope\s+\$end|\$var\s+\w+\s+(\d+)\s+(\S+)\s+(\S+)\s*(\S*)\s*\$end)", vcd):
    tok = m.group(0)
    if tok.startswith("$scope"):
        scope_stack.append(cur_scope[:])
        cur_scope.append(m.group(2))
    elif tok.startswith("$upscope"):
        cur_scope = scope_stack.pop() if scope_stack else []
    else:
        width, vid, ref = int(m.group(3)), m.group(4), m.group(5)
        name = m.group(6) or ""
        full = ".".join(cur_scope + [ref + name.replace(" ", "")])
        idmap[vid] = (full, width)

def find_code(pattern):
    for vid, (full, width) in idmap.items():
        if re.search(pattern, full):
            return vid, width
    return None, None

so_codes = {}
for b in range(4):
    vid, width = find_code(r"tb_scan_shift\.scan_out(\[%d\])?$" % b)
    # fallback: 名字恰好 scan_out 且 4 位 (tb 层 wire)
    if vid is None:
        for v2, (full, w2) in idmap.items():
            if full.startswith("tb_scan_shift.scan_out"):
                vid, width = v2, w2
                break
    if vid:
        so_codes[b] = (vid, width)
err_code, err_width = None, None
for vid, (full, width) in idmap.items():
    if full.startswith("tb_scan_shift.err"):
        err_code, err_width = vid, width

# 事件回放 (只保留值变化)
events = []
for line in vcd.split("\n"):
    line = line.strip()
    if not line or line.startswith("$"):
        continue
    if line.startswith("#"):
        cur_time = int(line[1:])
    elif line[0] in "01xz":
        events.append((cur_time, line[0], line[1:]))
    elif line[0] == "b":
        parts = line[1:].split(" ", 1)
        if len(parts) == 2:
            events.append((cur_time, parts[0], parts[1]))

state = {}
def lookup(vid, width):
    if vid not in state:
        return None, True
    v = state[vid]
    return v, ("x" in v or "z" in v)

check_ok = check_total = check_fail = 0
final_err = None
# 从 clk 波形动态推导 negedge 时刻 (不假设时间基)
clk_code = None
for vid, (full, width) in idmap.items():
    if full.startswith("tb_scan_shift.clk"):
        clk_code = vid
        break
clk_events = [(t, v) for (t, v, vid) in events if vid == clk_code]
neg_edges, prev = set(), None
for t, v in sorted(clk_events):
    if prev == "1" and v == "0":
        neg_edges.add(t)
    prev = v
neg_edges = sorted(neg_edges)[:462]
event_times = set(t for t, *_ in events)
all_times = sorted(event_times | set(neg_edges))
ev_at = {}
for (t, v, vid) in events:
    ev_at.setdefault(t, []).append((v, vid))
for t in all_times:
    if t in ev_at:
        for (v, vid) in ev_at[t]:
            state[vid] = v
    if t in neg_edges:
        M = neg_edges.index(t) + 1
        for b, (vid, width) in so_codes.items():
            if vid is None:
                continue
            val, isx = lookup(vid, width)
            if isx or val is None:
                continue
            if M >= lens[b] + 1 and M <= NCYC + 1:
                if M - (lens[b] + 1) >= len(seql[b]):
                    print("DEBUG M=%d b=%d L=%d idx=%d len=%d" % (M, b, lens[b], M-(lens[b]+1), len(seql[b])))
                    continue
                check_total += 1
                exp = seql[b][M - (lens[b] + 1)]
                got = ((int(val, 2) >> b) & 1) if width > 1 else (1 if val == "1" else 0)
                if got == exp:
                    check_ok += 1
                else:
                    check_fail += 1
        if err_code:
            v, isx = lookup(err_code, err_width)
            if not isx and v:
                try:
                    final_err = int(v, 2)
                except ValueError:
                    final_err = None

chain_verify = {
    "sim": "yosys sim (liberty 行为模型, 460 周期移位)",
    "vcd": "chain_sim.vcd",
    "checks": check_total, "matched": check_ok, "mismatched": check_fail,
    "tb_err_counter_final": final_err,
    "result": "PASS" if (check_fail == 0 and check_total > 0 and final_err == 0) else "FAIL",
}
json.dump(chain_verify, open("chain_verify.json", "w"), indent=2, ensure_ascii=False)
print("CHAIN VERIFY:", json.dumps(chain_verify, ensure_ascii=False))
