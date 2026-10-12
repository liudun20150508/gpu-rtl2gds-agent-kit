#!/usr/bin/env bash
# =============================================================================
# 02_synth.sh — Yosys 综合 + 映射 (Nangate45, 800 MHz 基线)
#   输出: out/Vortex_syn.v (门级网表) + reports/ (面积/单元/寄存器报告)
#   大阵列 SRAM 由 VX_dp_ram_asic/VX_sp_ram_asic 黑盒覆盖, 面积单独估算
# =============================================================================
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VORTEX="$ROOT/vortex"
BUILD="$ROOT/build/vortex_${PRESET:-base}"
export PATH="/opt/homebrew/opt/gnu-sed/libexec/gnubin:/opt/homebrew/bin:$PATH"

CLOCK_FREQ="${CLOCK_FREQ:-800}"
PERIOD_NS="$(python3 -c "print(1000/$CLOCK_FREQ)")"
LIB="$VORTEX/hw/syn/libs/NangateOpenCellLibrary_typical.lib"

mkdir -p "$BUILD/out" "$BUILD/reports"

# ---- 生成 synth.ys ----
cat > "$BUILD/out/synth.ys" << YS
read_liberty -lib $LIB
read_verilog -sv $BUILD/project.v
hierarchy -check -top Vortex
proc
opt
fsm; opt
wreduce; share; opt
memory_dff
opt
memory_map
opt
techmap; opt
write_verilog -noattr -noexpr -renameprefix syn_ $BUILD/out/Vortex_syn.v
write_json $BUILD/out/Vortex.json
dfflibmap -liberty $LIB
abc -D $PERIOD_NS -liberty $LIB
write_verilog -noattr -noexpr $BUILD/out/Vortex_mapped.v
YS

echo "[02-synth] CLOCK_FREQ=${CLOCK_FREQ}MHz period=${PERIOD_NS}ns"
echo "[02-synth] yosys -s synth.ys (大设计, 预计 10~30 分钟)"
yosys -s "$BUILD/out/synth.ys" -l "$BUILD/reports/yosys.log" 2>&1 | tail -25

# 黑盒 SRAM 模块定义 (write_verilog 不输出空 blackbox 定义, 手工附加)
cat $VORTEX/hw/syn/libs/no_mem/VX_dp_ram_asic.v >> $BUILD/out/Vortex_mapped.v
cat $VORTEX/hw/syn/libs/no_mem/VX_sp_ram_asic.v >> $BUILD/out/Vortex_mapped.v

echo "[02-synth] === 面积/单元统计 (独立 stat, 保证输出) ==="
yosys -p "read_liberty -lib $LIB; read_verilog -sv $BUILD/out/Vortex_mapped.v; hierarchy -check -top Vortex; stat -liberty $LIB" > "$BUILD/reports/stat_full.rpt" 2>&1
grep -m4 -E "Chip area for top module|of which used for sequential" "$BUILD/reports/stat_full.rpt"

echo "[02-synth] === SRAM 黑盒面积估算 ==="
python3 "$VORTEX/hw/syn/yosys/sram_cost.py" "$BUILD/out/Vortex.json" \
    --top Vortex --modules VX_dp_ram_asic VX_sp_ram_asic \
    --width-ports wdata,rdata --addr-ports addr,waddr,raddr \
    --bit-area 0.1 --overhead 100.0 | tee "$BUILD/reports/sram_area.rpt"

echo "[02-synth] DONE"
