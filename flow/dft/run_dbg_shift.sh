#!/bin/sh
# 判决性实验: 装载 -> 卸载 逐拍打印, 定位 04 阶段相位差
# 用法: sh flow/dft/run_dbg_shift.sh [0|1]   (1 = 插入捕获拍)
set -e
CAP="${1:-0}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
OUT="$ROOT/results/dft/04_verify"
LIB="${SKY130_LIB:-${ORFS_ROOT:-$HOME/tools/OpenROAD-flow-scripts/flow}/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib}"

cd "$OUT"
if [ ! -f tiny_npu_scan.v ]; then
  ln -s "$ROOT/results/dft/02_scan/tiny_npu_scan.v" tiny_npu_scan.v
fi

cat > dbg_shift.ys <<EOF
read_verilog tiny_npu_scan.v
read_liberty -ignore_miss_func $LIB
read_verilog tb_dbg_shift.v
hierarchy -top tb_dbg_shift -check
proc
sim -clock clk -n 400
EOF

CAPTURE="$CAP" python3 "$HERE/dbg_shift.py" > /tmp/dbg_shift_gen.log 2>&1 || { tail -20 /tmp/dbg_shift_gen.log; exit 1; }
yosys -Q dbg_shift.ys > /tmp/dbg_shift.log 2>&1
echo "=== yosys tail ==="
tail -12 /tmp/dbg_shift.log
echo "=== U/L lines ==="
grep -E "^(U|L) " /tmp/dbg_shift.log | head -60
