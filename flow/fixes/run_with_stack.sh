#!/usr/bin/env bash
# =============================================================
# DRT 栈溢出修复包装（Signal 11 / boost::polygon::MaxCover 深度递归）
#
# 现象：detail route 阶段 openroad 崩溃，报 Signal 11，栈回溯落在
#       boost::polygon::MaxCover —— 是布线器递归深度超过默认栈上限，
#       不是设计或 PDK 的问题，重跑多少次都一样。
# 修法：把栈上限抬到 64MB 再跑同一条命令。
#
# 用法（直接跑命令）：
#   ./run_with_stack.sh openroad -exit flow/openroad/04_route.tcl
#
# 用法（给当前 shell 生效，随后所有命令都抬高）：
#   source ./run_with_stack.sh --export
#
# 自定义大小：
#   STACK_KB=131072 ./run_with_stack.sh <命令...>
#
# 说明：ulimit 只影响当前进程及其子进程，所以必须包在「跑布线器」这一层，
#       在流程脚本外层设置没有用。
# =============================================================
set -euo pipefail

STACK_KB="${STACK_KB:-65536}"   # 64MB

raise_stack() {
    local cur
    cur="$(ulimit -s 2>/dev/null || echo unknown)"
    if ! ulimit -s "$STACK_KB" 2>/dev/null; then
        echo "警告: 无法把栈上限设为 ${STACK_KB}KB（当前 ${cur}KB）。" >&2
        echo "      若仍出现 Signal 11，可能需要 sudo 或换更小的值。" >&2
        return 1
    fi
    echo "栈上限: ${cur}KB → $(ulimit -s)KB" >&2
    return 0
}

case "${1:-}" in
    -h|--help)
        sed -n '2,26p' "$0"
        exit 0 ;;
    --export)
        # 被 source 时抬高当前 shell；直接执行时也给出可用提示
        raise_stack || true
        echo "已在当前 shell 生效（仅本 shell 及其子进程）。" >&2
        ;;
    --check)
        echo "当前 shell 栈上限: $(ulimit -s 2>/dev/null || echo 未知)KB"
        echo "本脚本默认值:      ${STACK_KB}KB"
        echo "硬上限:            $(ulimit -Hs 2>/dev/null || echo 未知)KB"
        ;;
    "")
        echo "用法: $0 <命令...>   或   source $0 --export   （--help 看说明）" >&2
        exit 2 ;;
    *)
        raise_stack || true
        exec "$@"
        ;;
esac
