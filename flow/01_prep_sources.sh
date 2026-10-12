#!/usr/bin/env bash
# =============================================================================
# 01_prep_sources.sh — RTL 准备阶段
#   VX_config.toml -> VX_config.vh/VX_types.vh (配置头生成)
#   Verilator -E 逐文件预处理(`include / `ifdef / 宏展开)
#   sv2v: SystemVerilog -> Verilog (Yosys 兼容网表输入)
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VORTEX="$ROOT/vortex"
PRESET="${PRESET:-base}"          # base=基线GPU | llm=大模型推理配置(TCU FP8/INT8)
BUILD="$ROOT/build/vortex_$PRESET"
SRC="$BUILD/src"

export XLEN="${XLEN:-64}"
NUM_CORES="${NUM_CORES:-1}"
export PATH="/opt/homebrew/opt/gnu-sed/libexec/gnubin:/opt/homebrew/bin:$PATH"

echo "[01-prep] PRESET=$PRESET XLEN=$XLEN NUM_CORES=$NUM_CORES"

# 1. 从 TOML 生成 Verilog 配置头
mkdir -p "$BUILD/hw"
python3 "$VORTEX/ci/gen_config.py" --config "$VORTEX/VX_config.toml" \
    --output "$BUILD/hw/VX_config.vh" --format verilog
python3 "$VORTEX/ci/gen_config.py" --config "$VORTEX/VX_types.toml" \
    --output "$BUILD/hw/VX_types.vh" --format verilog --resolved

# 2. 解析配置 -> 宏定义列表
BASE_CFG="-DSYNTHESIS -DASIC -DYOSYS -DVX_CFG_NUM_CLUSTERS=1 -DVX_CFG_NUM_CORES=$NUM_CORES -DVX_CFG_XLEN=$XLEN"
# LLM 推理/微调配置: 张量核 + FP8/INT8 (KV cache 由 L1/LMEM 承载)
if [ "$PRESET" = "llm" ]; then
    BASE_CFG="$BASE_CFG -DVX_CFG_EXT_TCU_ENABLE -DVX_CFG_TCU_FP8_ENABLE -DVX_CFG_TCU_INT8_ENABLE -DVX_CFG_TCU_SPARSE_ENABLE"
fi
XCONFIGS="$(python3 "$VORTEX/ci/gen_config.py" --config="$VORTEX/VX_config.toml" --cflags="$BASE_CFG")"

# 3. Verilator 逐文件预处理(宏展开 + include 内联)
RTL_DIRS=(
    "$VORTEX/hw/rtl" "$VORTEX/hw/rtl/libs" "$VORTEX/hw/rtl/interfaces"
    "$VORTEX/hw/rtl/core" "$VORTEX/hw/rtl/mem" "$VORTEX/hw/rtl/cache"
    "$VORTEX/hw/rtl/fpu" "$VORTEX/hw/rtl/tcu" "$VORTEX/hw/rtl/tcu/tfr"
    "$VORTEX/hw/syn/libs/no_mem"
)
INC_ARGS=()
for d in "${RTL_DIRS[@]}"; do INC_ARGS+=("-I$d"); done
INC_ARGS+=("-I$VORTEX/hw" "-I$BUILD/hw" "-I$VORTEX/sw")
DEF_ARGS=()
for d in $XCONFIGS; do DEF_ARGS+=("$d"); done

rm -rf "$SRC"; mkdir -p "$SRC"
echo "[01-prep] verilator -E preprocessing ..."
for dir in "${RTL_DIRS[@]}"; do
    for f in "$dir"/*.sv "$dir"/*.v; do
        [ -f "$f" ] || continue
        out="$SRC/$(basename "$f")"
        verilator "${DEF_ARGS[@]}" "${INC_ARGS[@]}" -E -P "$f" > "$out" 2>"$out.err" || {
            echo "verilator FAILED: $f"; cat "$out.err" | head -5; exit 1; }
    done
done
# 去掉 modport 限定符(Vivado/Yosys 兼容)
for f in "$SRC"/*.sv; do sed -i 's/\.\(master\|slave\)\b//g' "$f"; done
echo "[01-prep] preprocessed files: $(ls "$SRC" | wc -l)"

# 4. sv2v: SV -> Verilog 单文件
echo "[01-prep] sv2v conversion ..."
"$VORTEX/hw/scripts/sv2v.sh" -tVortex -I"$SRC" -o"$BUILD/project.v" > "$BUILD/sv2v.log" 2>&1 || {
    echo "sv2v FAILED"; tail -20 "$BUILD/sv2v.log"; exit 1; }
sed -i -E '/^[[:space:]]*[$](finish|display|fatal|error|warning|info|stop)/d' "$BUILD/project.v"

echo "$BUILD/project.v" > "$BUILD/sources.txt"
wc -l "$BUILD/project.v"
echo "[01-prep] DONE"
