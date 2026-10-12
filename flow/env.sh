#!/bin/bash
# =============================================================
# rtl2gds-agent-kit · 环境参数化
#
# 本仓库不含任何个人绝对路径。所有工具/库位置通过环境变量注入。
#
#   source flow/env.sh            # 载入参数（默认值 + 你的覆盖）
#   bash   flow/env.sh --check    # 自检：打印解析结果并校验文件是否存在
#   bash   flow/env.sh --export   # 打印可直接 eval 的 export 语句
#
# 覆盖方式（在调用前 export 即可）：
#   export ORFS_ROOT=/path/to/OpenROAD-flow-scripts/flow
#   export SKY130_LIB=/path/to/<工艺>.lib
#   export PDK_ROOT=/path/to/pdk
# =============================================================
set -uo pipefail

# ---- 工具与流程根目录 ----
export ORFS_ROOT="${ORFS_ROOT:-$HOME/tools/OpenROAD-flow-scripts/flow}"
export PDK_ROOT="${PDK_ROOT:-}"

# ---- 目标工艺时序库（变量名为历史命名，语义 = 当前目标工艺的时序库）----
export SKY130_LIB="${SKY130_LIB:-$ORFS_ROOT/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib}"

# ---- 可执行文件（找不到就留空，由 --check 报告）----
export OPENROAD_EXE="${OPENROAD_EXE:-$(command -v openroad 2>/dev/null || true)}"
export YOSYS_EXE="${YOSYS_EXE:-$(command -v yosys 2>/dev/null || true)}"
export KLAYOUT_CMD="${KLAYOUT_CMD:-$(command -v klayout 2>/dev/null || true)}"

# ---- 设计源（示例设计；换成自己的设计时覆盖它）----
export TINYNPU_RTL="${TINYNPU_RTL:-$PWD/tiny-npu}"
export DESIGN_TOP="${DESIGN_TOP:-top}"

# ---- 并行度：大型设计在 32GB 机器上必须 -j1，否则 route 阶段 OOM ----
export NPROC="${NPROC:-1}"

_check() {
    local ok=0
    printf '%-14s %s\n' "变量" "解析结果"
    printf '%-14s %s\n' "ORFS_ROOT" "$ORFS_ROOT"
    printf '%-14s %s\n' "SKY130_LIB" "$SKY130_LIB"
    printf '%-14s %s\n' "PDK_ROOT" "${PDK_ROOT:-<未设置>}"
    printf '%-14s %s\n' "OPENROAD_EXE" "${OPENROAD_EXE:-<未找到>}"
    printf '%-14s %s\n' "YOSYS_EXE" "${YOSYS_EXE:-<未找到>}"
    printf '%-14s %s\n' "KLAYOUT_CMD" "${KLAYOUT_CMD:-<未找到>}"
    printf '%-14s %s\n' "NPROC" "$NPROC"
    echo
    for spec in "ORFS_ROOT:$ORFS_ROOT" "SKY130_LIB:$SKY130_LIB"; do
        name="${spec%%:*}"; path="${spec#*:}"
        if [ -e "$path" ]; then
            echo "  [OK]   $name 存在"
        else
            echo "  [MISS] $name 不存在: $path"
            ok=1
        fi
    done
    for tool in OPENROAD_EXE YOSYS_EXE KLAYOUT_CMD; do
        if [ -n "${!tool:-}" ]; then echo "  [OK]   $tool = ${!tool}"; else echo "  [WARN] $tool 未找到（跑对应阶段前需安装）"; fi
    done
    echo
    if [ "$ok" -eq 0 ]; then echo "环境自检通过。"; else echo "环境自检未通过：请设置缺失变量后重试。"; fi
    return "$ok"
}

if [ "${1:-}" = "--check" ]; then
    _check
elif [ "${1:-}" = "--export" ]; then
    for v in ORFS_ROOT PDK_ROOT SKY130_LIB OPENROAD_EXE YOSYS_EXE KLAYOUT_CMD TINYNPU_RTL DESIGN_TOP NPROC; do
        printf 'export %s=%q\n' "$v" "${!v}"
    done
fi
