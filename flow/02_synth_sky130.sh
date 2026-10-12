#!/usr/bin/env bash
# =============================================================================
# 02_synth_sky130.sh — Yosys 综合 + SKY130 映射 (llm/TCU 配置, 50MHz 基线)
#   输出: out/Vortex_mapped_sky130.v + reports/sky130_yosys.log
#   与 02_synth.sh 同构, 仅换库/周期; 大阵列 SRAM 黑盒策略不变
# =============================================================================
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VORTEX="$ROOT/vortex"
BUILD="$ROOT/build/vortex_${PRESET:-llm}"
export PATH="/opt/homebrew/opt/gnu-sed/libexec/gnubin:/opt/homebrew/bin:$PATH"

CLOCK_FREQ="${CLOCK_FREQ:-50}"   # SKY130 保守 50MHz = 20ns
PERIOD_NS="$(python3 -c "print(1000/$CLOCK_FREQ)")"
# 双库策略 (2026-08-19 修复 $_DFFE_PP_ cannot be legalized):
#   dffmap 库: Q 引脚 function 恢复为 IQ/IQ_N + ff 组补 clear/preset (dfflibmap 识别所需)
#   patched 库: function 为 D/!D + 三态 dont_use (abc/OpenSTA 解析所需)
LIB_DFFMAP="$BUILD/apr/sky130_fd_sc_hd__tt_025C_1v80_dffmap.lib"
LIB="$BUILD/apr/sky130_fd_sc_hd__tt_025C_1v80_patched.lib"

mkdir -p "$BUILD/out" "$BUILD/reports"

cat > "$BUILD/out/synth_sky130.ys" << YS
read_liberty -lib $LIB_DFFMAP
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
write_verilog -noattr -noexpr -renameprefix syn_ $BUILD/out/Vortex_syn_sky130.v
write_json $BUILD/out/Vortex_sky130.json
dfflibmap -liberty $LIB_DFFMAP
abc -D $PERIOD_NS -liberty $LIB
write_verilog -noattr -noexpr $BUILD/out/Vortex_mapped_sky130.v
YS

echo "[02-synth-sky130] CLOCK_FREQ=${CLOCK_FREQ}MHz period=${PERIOD_NS}ns"
echo "[02-synth-sky130] yosys -s synth_sky130.ys (预计 10~30 分钟)"
yosys -s "$BUILD/out/synth_sky130.ys" -l "$BUILD/reports/yosys_sky130.log" 2>&1 | tail -25

cat $VORTEX/hw/syn/libs/no_mem/VX_dp_ram_asic.v >> $BUILD/out/Vortex_mapped_sky130.v
cat $VORTEX/hw/syn/libs/no_mem/VX_sp_ram_asic.v >> $BUILD/out/Vortex_mapped_sky130.v

echo "[02-synth-sky130] === 面积/单元统计 ==="
yosys -p "read_liberty -lib $LIB; read_verilog -sv $BUILD/out/Vortex_mapped_sky130.v; hierarchy -check -top Vortex; stat -liberty $LIB" > "$BUILD/reports/stat_sky130_full.rpt" 2>&1
grep -m4 -E "Chip area for top module|of which used for sequential" "$BUILD/reports/stat_sky130_full.rpt"

echo "[02-synth-sky130] === SRAM 黑盒面积估算 ==="
python3 "$VORTEX/hw/syn/yosys/sram_cost.py" "$BUILD/out/Vortex_sky130.json" \
    --top Vortex --modules VX_dp_ram_asic VX_sp_ram_asic \
    --width-ports wdata,rdata --addr-ports addr,waddr,raddr \
    --bit-area 0.35 > "$BUILD/reports/sram_sky130_area.rpt" 2>&1 || true
tail -5 "$BUILD/reports/sram_sky130_area.rpt"
echo "[02-synth-sky130] DONE"
