#!/bin/bash
# =============================================================
# DFT Demo · Stage 01 逻辑综合 + 门级网表生成
# 定位: 综合 / DFT 流程（开源工艺可测性设计链）
# 设计: tinyNPU (LLM 推理加速 NPU, $TINYNPU_RTL)
# 工具: Yosys + SKY130 HD (tt_025C_1v80)
# 输入: $TINYNPU_RTL/rtl  (36 个 SystemVerilog 源文件)
# 输出: results/dft/01_synth/
# =============================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
OUT="$ROOT/results/dft/01_synth"
LIB="${SKY130_LIB:-${ORFS_ROOT:-$HOME/tools/OpenROAD-flow-scripts/flow}/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib}"
RTL="${TINYNPU_RTL:-$ROOT/tiny-npu/rtl}"
mkdir -p "$OUT"
cd "$OUT"

cat > synth.ys <<YSEOF
# tinyNPU 综合脚本 (DFT demo 复现版, 与 results/synth/tiny-npu 同源同选项)
read_slang $RTL/pkg/fixed_pkg.sv $RTL/pkg/isa_pkg.sv $RTL/pkg/kv_pkg.sv $RTL/pkg/npu_pkg.sv $RTL/bus/axi_types.sv $RTL/bus/axi_dma_rd.sv $RTL/bus/axi_dma_wr.sv $RTL/bus/axi_lite_regs.sv $RTL/ctrl/addr_gen.sv $RTL/ctrl/barrier.sv $RTL/ctrl/scoreboard.sv $RTL/ctrl/ucode_decode.sv $RTL/ctrl/ucode_fetch.sv $RTL/gemm/gemm_ctrl.sv $RTL/gemm/gemm_post.sv $RTL/gemm/mac_int8.sv $RTL/gemm/pe.sv $RTL/gemm/systolic_array.sv $RTL/mem/banked_sram.sv $RTL/mem/kv_cache_bank.sv $RTL/mem/sram_dp.sv $RTL/ops/exp_lut.sv $RTL/ops/gelu_engine.sv $RTL/ops/gelu_lut.sv $RTL/ops/layernorm_engine.sv $RTL/ops/mean_var_engine.sv $RTL/ops/recip_lut.sv $RTL/ops/reduce_max.sv $RTL/ops/reduce_sum.sv $RTL/ops/rmsnorm_engine.sv $RTL/ops/rope_engine.sv $RTL/ops/rsqrt_lut.sv $RTL/ops/silu_lut.sv $RTL/ops/softmax_engine.sv $RTL/ops/vec_engine.sv $RTL/top.sv
hierarchy -top top -check
proc
opt
memory -nomap
wreduce
techmap
opt -fast
dfflibmap -liberty $LIB
abc -liberty $LIB -D 10000
opt_clean
stat -liberty $LIB
write_verilog -noattr tiny_npu_netlist.v
write_json tiny_npu.json
YSEOF

yosys -l synth.log synth.ys
echo "=== 统计摘要 ==="
grep -E "Chip area|Number of cells|sky130_fd_sc_hd__dfrtp|sky130_fd_sc_hd__df" synth.log | tail -8
echo "=== 单元类型分布 (top 10) ==="
grep -oE "sky130_fd_sc_hd__[a-z0-9_]+" tiny_npu_netlist.v | sort | uniq -c | sort -rn | head -10
echo "=== 时序逻辑占比 ==="
python3 - "$OUT/tiny_npu_netlist.v" <<'PYEOF'
import sys, re
t=open(sys.argv[1]).read()
dff=len(re.findall(r'sky130_fd_sc_hd__dfrtp_1\s+', t))
cells=len(re.findall(r'^\s*sky130_fd_sc_hd__\w+\s+_\d+_\s*\(', t, re.M))
print(f"总实例={cells}  DFF={dff}  时序占比={dff/cells*100:.1f}%")
PYEOF
