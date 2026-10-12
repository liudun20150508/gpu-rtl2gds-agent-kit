#!/usr/bin/env bash
# =============================================================================
# 03_sta.sh — 时序签核 (OpenSTA 3.1, Nangate45 typical)
#   OpenSTA 解析器限制: 不支持 signed 声明/字面量/黑盒参数 -> Python 净化网表
# =============================================================================
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VORTEX="$ROOT/vortex"
BUILD="$ROOT/build/vortex_${PRESET:-base}"
export PATH="/opt/homebrew/opt/gnu-sed/libexec/gnubin:/opt/homebrew/bin:$PATH"

CLOCK_FREQ="${CLOCK_FREQ:-800}"
PERIOD_NS="$(python3 -c "print(1000/$CLOCK_FREQ)")"
LIB="$VORTEX/hw/syn/libs/NangateOpenCellLibrary_typical.lib"
NETLIST="$BUILD/out/Vortex_mapped.v"

# ---- 净化网表 (OpenSTA 兼容) ----
CLEAN_NETLIST="$BUILD/out/Vortex_mapped_sta.v"
python3 - "$NETLIST" "$CLEAN_NETLIST" << 'CLEANEOF'
import re, sys
src, dst = sys.argv[1], sys.argv[2]
t = open(src, encoding="utf-8", errors="ignore").read()
t = t.replace("wire signed ", "wire ")                    # OpenSTA 不支持 signed 声明
t = re.sub(r"(\d+)'s([dhbo])", r"\1'\2", t)               # OpenSTA 不支持有符号字面量
t = re.sub(r"module (VX_[ds]p_ram_asic) #\(.*?\)\s*\(",   # 黑盒 RAM 参数声明
           r"module \1 (", t, flags=re.S)
t = re.sub(r"(VX_[ds]p_ram_asic)\s*#\(.*?\)\s*(\\[^ ]+)\s*\(",  # 实例参数覆盖
           r"\1 \2 (", t, flags=re.S)
t = re.sub(r"(module VX_[ds]p_ram_asic \(.*?\))\s*;.*?endmodule",  # 黑盒行为体移除
           r"\1;\nendmodule", t, flags=re.S)
t = t.replace("[WRENW-1:0]", "[255:0]")                   # 黑盒端口宽度固定化
t = t.replace("[ADDRW-1:0]", "[63:0]")
t = t.replace("[DATAW-1:0]", "[2047:0]")
open(dst, "w").write(t)
CLEANEOF

# ---- 生成 STA 脚本 ----
mkdir -p "$BUILD/reports"
cat > "$BUILD/out/sta.tcl" << TCL
read_liberty $LIB
read_verilog $CLEAN_NETLIST
link_design Vortex

create_clock -name clk -period $PERIOD_NS [get_ports clk]
set_clock_uncertainty [expr $PERIOD_NS * 0.02] [get_clocks clk]
create_clock -name ext_clk -period $PERIOD_NS
set in_ports {}
foreach p [all_inputs] { if {\$p ne [get_ports clk]} { lappend in_ports \$p } }
set_input_delay  [expr $PERIOD_NS * 0.05] -clock ext_clk \$in_ports
set_output_delay [expr $PERIOD_NS * 0.05] -clock ext_clk [all_outputs]
set_ideal_network [get_ports reset]

puts "==== WNS/TNS (setup) ===="
report_worst_slack -max
report_wns
report_tns
puts "==== WNS (hold) ===="
report_worst_slack -min
puts "==== 关键路径 Top10 ===="
report_checks -path_delay max -group_path_count 10
puts "==== 面积 ===="
puts "area 见 yosys stat 报告 (stat_full.rpt)"
exit
TCL

echo "[03-sta] CLOCK_FREQ=${CLOCK_FREQ}MHz period=${PERIOD_NS}ns"
sta -exit "$BUILD/out/sta.tcl" 2>&1 | tee "$BUILD/reports/sta.rpt" | tail -50
echo "[03-sta] DONE -> $BUILD/reports/sta.rpt"
