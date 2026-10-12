#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""判决性实验: 装载 -> (可选捕获) -> 卸载, 逐拍打印 scan_out, 定位 04 的相位差
- 四条链装载同一条 179bit 伪随机序列 (链 1~3 只有 178 级, 首位会被移出丢弃)
- 卸载阶段连续打印 SHIFT+12 拍
- 自洽判据 (CAPTURE=0): 卸载流应等于装载流 (首位进 = 首位出), 偏移即为相位误差
用法: CAPTURE=0|1 python3 dbg_shift.py
"""
import os, re, subprocess, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SCAN = os.path.join(ROOT, "results/dft/02_scan/tiny_npu_scan.v")
OUT = os.path.join(ROOT, "results/dft/04_verify")
LIB = os.environ.get("SKY130_LIB") or os.path.expanduser(os.environ.get("ORFS_ROOT", "~/tools/OpenROAD-flow-scripts/flow") + "/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib")
SHIFT = 179
CAPTURE = int(os.environ.get("CAPTURE", "0"))

rng = random.Random(7)
seq = [rng.randint(0, 1) for _ in range(SHIFT)]
print("load seq (index 0 first):", "".join(str(b) for b in seq))

t_scan = open(SCAN).read()
port_decls = []
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
conn = [".clk(clk)", ".rst_n(1'b1)", ".scan_en(scan_en)", ".scan_in(scan_in)", ".scan_out(scan_out)"]
for (nm, msb, lsb) in port_decls:
    if msb is None:
        conn.append(".%s(1'b0)" % nm)
    else:
        conn.append(".%s(%d'b0)" % (nm, abs(msb - lsb) + 1))
outports = []
for d, names in re.findall(r"^\s*(output)\s+(.*?);", t_scan, re.M):
    for raw in names.split(","):
        nm = raw.strip().split()
        nm = nm[-1] if nm else ""
        if nm and nm != "scan_out":
            outports.append(nm)
for i, p in enumerate(outports):
    conn.append(".%s(_wo_%d)" % (p, i))

nxt = "2" if CAPTURE else "2"          # state 1 -> state 2
tb = []
tb.append("module tb_dbg_shift;")
tb.append("  reg clk = 0; reg scan_en = 1; reg [3:0] scan_in = 0;")
tb.append("  wire [3:0] scan_out;")
tb.append("  integer cyc = 0; integer state = 0;")
# ld[i] = seq[i]
tb.append("  reg [%d:0] ld = %d'b%s;" % (SHIFT - 1, SHIFT,
                                         "".join(str(b) for b in reversed(seq))))
for i in range(len(outports)):
    tb.append("  wire _wo_%d;" % i)
tb.append("  top dut (" + ", ".join(conn) + ");")
tb.append("  always #1 clk = ~clk;")
tb.append("  always @(posedge clk) begin")
tb.append("    case (state)")
if CAPTURE:
    tb.append("      0: begin cyc = cyc + 1; if (cyc == %d) begin state = 1; cyc = 0; end end" % (SHIFT + 1))
    tb.append("      1: state = 2;")
else:
    tb.append("      0: begin cyc = cyc + 1; if (cyc == %d) begin state = 2; cyc = 0; end end" % (SHIFT))
tb.append("      2: begin cyc = cyc + 1; if (cyc == %d) $finish; end" % (SHIFT + 12))
tb.append("    endcase")
tb.append("  end")
tb.append("  always @(negedge clk) begin")
tb.append("    case (state)")
tb.append("      0: begin")
tb.append("        scan_en = 1;")
tb.append("        scan_in = (cyc == 0) ? 4'b0 : {4{ld[cyc-1]}};")
tb.append('        if (cyc >= 1) $display("L %0d %b", cyc, ld[cyc-1]);')
tb.append("      end")
if CAPTURE:
    tb.append("      1: begin scan_en = 0; end")
tb.append("      2: begin")
tb.append("        scan_en = 1; scan_in = 0;")
tb.append('        $display("U %0d %b%b%b%b", cyc, scan_out[0], scan_out[1], scan_out[2], scan_out[3]);')
tb.append("      end")
tb.append("    endcase")
tb.append("  end")
tb.append("endmodule")
open(os.path.join(OUT, "tb_dbg_shift.v"), "w").write("\n".join(tb) + "\n")

if not os.path.exists(os.path.join(OUT, "tiny_npu_scan.v")):
    os.symlink(SCAN, os.path.join(OUT, "tiny_npu_scan.v"))
os.chdir(OUT)
ndump = SHIFT + 12
ys = ("read_verilog tiny_npu_scan.v; read_liberty -ignore_miss_func %s; "
      "read_verilog tb_dbg_shift.v; hierarchy -top tb_dbg_shift -check; proc; "
      "sim -clock clk -n %d" % (LIB, 2 * (SHIFT + 14)))
r = subprocess.run(["yosys", "-Q", "-p", ys], capture_output=True, text=True)
U = {}
L = {}
for line in r.stdout.splitlines():
    m = re.match(r"U\s+(\d+)\s+(\d)(\d)(\d)(\d)", line.strip())
    if m:
        U[int(m.group(1))] = m.group(2) + m.group(3) + m.group(4) + m.group(5)
    m = re.match(r"L\s+(\d+)\s+(\d)", line.strip())
    if m:
        L[int(m.group(1))] = m.group(2)
print("U samples:", len(U))
stream = "".join(U[k][0] for k in sorted(U))
print("unload chain0 (cyc=%d..%d): %s" % (min(U), max(U), stream))
expect = "".join(str(b) for b in seq)
print("load   seq            : %s" % expect)
# 对齐搜索
best = None
for off in range(0, 25):
    win = stream[off:off + SHIFT]
    if len(win) < SHIFT:
        break
    if win == expect:
        best = off
        break
print("CAPTURE=%d  ->  unload 相对 load 序列的偏移 = %s" % (CAPTURE, best))
if best is None:
    for off in range(0, 25):
        win = stream[off:off + SHIFT]
        if len(win) < SHIFT:
            break
        nd = sum(1 for a, b in zip(win, expect) if a != b)
        print("   off=%2d  ndiff=%d" % (off, nd))
