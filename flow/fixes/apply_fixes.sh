#!/usr/bin/env bash
# =============================================================
# 后端流程修复脚本总入口
#
# 这里收的都是「流程跑挂了、原因明确、改一下就好，但下次还会忘」的修复。
# 每条修复都对应 rules/pitfalls.yaml 里的一个坑，id 一一对齐。
#
# 用法：
#   ./apply_fixes.sh --list                       列出全部修复
#   ./apply_fixes.sh --show <id>                  看某条的症状、根因、用法
#   ./apply_fixes.sh --check                      环境自检（不需要输入文件的都跑）
#   ./apply_fixes.sh --check   <id> <参数...>     只诊断某一条，不改任何文件
#   ./apply_fixes.sh --apply   <id> <参数...>     应用某一条
#   ./apply_fixes.sh --selftest                   跑所有带内置样例的修复脚本
#
# 例子：
#   ./apply_fixes.sh --check  spef  build/6_final.spef
#   ./apply_fixes.sh --apply  spef  build/6_final.spef build/6_final_fixed.spef
#   ./apply_fixes.sh --apply  dfflib build/apr/sky130_fd_sc_hd__tt_025C_1v80.lib build/apr
#   ./apply_fixes.sh --apply  stack  openroad -exit 04_route.tcl
#
# 兼容 macOS 自带 bash 3.2：不使用关联数组。
# =============================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PY:-python3}"

FIX_IDS="spef cdl conb dfflib stack"

# ---------------------------------------------------------------- 元数据
fix_script() {
    case "$1" in
        spef)   echo "fix_spef_negidx.py" ;;
        cdl)    echo "fix_cdl.py" ;;
        conb)   echo "fix_conb_cdl.py" ;;
        dfflib) echo "gen_dff_libs.py" ;;
        stack)  echo "run_with_stack.sh" ;;
    esac
}

fix_title() {
    case "$1" in
        spef)   echo "SPEF 负索引毒 token（STA-1670）" ;;
        cdl)    echo "CDL 实例行缺单元名（LVS 前置）" ;;
        conb)   echo "conb tie cell 与版图提取不一致（LVS）" ;;
        dfflib) echo "双库策略：生成 dffmap / patched 两份 lib（DFF legalize 失败）" ;;
        stack)  echo "抬高栈上限跑布线（DRT Signal 11 / MaxCover 栈溢出）" ;;
    esac
}

fix_symptom() {
    case "$1" in
        spef)   echo "STA read_spef 报 [ERROR STA-1670] syntax error" ;;
        cdl)    echo "LVS 读不进网表 / 器件数对不上，CDL 里 X 行末尾没有单元名" ;;
        conb)   echo "LVS 卡在 conb 单元：原理图有实例、版图提取网表里没有" ;;
        dfflib) echo "综合报 \$_DFFE_PP_ cannot be legalized / DFF 映射不上" ;;
        stack)  echo "detail route 崩溃 Signal 11，栈回溯落在 boost::polygon::MaxCover" ;;
    esac
}

fix_usage() {
    case "$1" in
        spef)   echo "<in.spef> [out.spef]       缺 out.spef 时只统计不改" ;;
        cdl)    echo "<cdl> <6_final.v>         就地补单元名" ;;
        conb)   echo "<cdl>                     就地改写 tie 连接" ;;
        dfflib) echo "<原始.lib> <输出目录>      产出 <stem>_dffmap.lib 与 <stem>_patched.lib" ;;
        stack)  echo "<命令...>                  在抬高的栈上限里执行该命令" ;;
    esac
}

fix_needs_file() {
    case "$1" in
        stack) return 1 ;;   # 不需要输入文件
        *)     return 0 ;;
    esac
}

is_valid_id() {
    case " $FIX_IDS " in *" $1 "*) return 0 ;; *) return 1 ;; esac
}

# ---------------------------------------------------------------- 命令

cmd_list() {
    echo "可用的修复（id 与 rules/pitfalls.yaml 对齐）："
    echo
    for id in $FIX_IDS; do
        printf '  %-7s %s\n' "$id" "$(fix_title "$id")"
        printf '          %s\n' "$(fix_symptom "$id")"
        printf '          脚本: flow/fixes/%s    参数: %s\n\n' "$(fix_script "$id")" "$(fix_usage "$id")"
    done
    echo "看单条详情：./apply_fixes.sh --show <id>"
}

cmd_show() {
    local id="$1"
    echo "=== $id — $(fix_title "$id") ==="
    echo
    echo "症状: $(fix_symptom "$id")"
    echo "用法: $(fix_script "$id") $(fix_usage "$id")"
    echo
    echo "--- 脚本自带说明 ---"
    local s="$HERE/$(fix_script "$id")"
    case "$s" in
        *.py) "$PY" "$s" --help ;;
        *.sh) bash "$s" --help ;;
    esac
}

run_check() {
    local id="$1"; shift
    local s="$HERE/$(fix_script "$id")"
    case "$id" in
        stack)
            bash "$s" --check ;;
        spef)
            if [ $# -eq 0 ]; then
                echo "需要参数：$(fix_usage spef)"
                echo "快速判断是否中招：在 SPEF 里搜毒 token 数量 ——"
                echo "  grep -c '\\[-[0-9]' <file.spef>"
                return 0
            fi
            "$PY" "$s" --check "$@" ;;
        dfflib)
            if [ $# -eq 0 ]; then
                echo "需要参数：$(fix_usage dfflib)"
                echo "建议先跑结构探测：$PY flow/fixes/gen_dff_libs.py --inspect <原始.lib>"
                return 0
            fi
            "$PY" "$s" --check "$@" ;;
        *)
            if [ $# -eq 0 ]; then
                echo "需要参数：$(fix_usage "$id")"
                return 0
            fi
            "$PY" "$s" --check "$@" ;;
    esac
}

cmd_check() {
    if [ $# -gt 0 ]; then
        local id="$1"; shift
        if ! is_valid_id "$id"; then
            echo "未知修复 id：$id（可用：$FIX_IDS）" >&2
            return 2
        fi
        printf '=== %s — %s ===\n' "$id" "$(fix_title "$id")"
        run_check "$id" "$@"
        return $?
    fi

    echo "=== 环境自检（不改任何文件）==="
    echo
    local rc=0
    for id in $FIX_IDS; do
        printf -- '--- %s: %s\n' "$id" "$(fix_title "$id")"
        if fix_needs_file "$id"; then
            echo "    需要输入文件，跳过自动检测。用法：$(fix_script "$id") $(fix_usage "$id")"
            echo "    查具体文件：./apply_fixes.sh --check $id <参数>"
        else
            run_check "$id" || rc=1
        fi
        echo
    done
    echo "提示：这些脚本大多默认就地修改目标文件，先复制一份再动生产产物。"
    return $rc
}

cmd_selftest() {
    local rc=0
    echo "=== 跑各修复脚本的内置样例 ==="
    echo
    for pair in "fix_spef_negidx.py --selftest" "gen_dff_libs.py --selftest"; do
        # shellcheck disable=SC2086
        set -- $pair
        echo "--- $1"
        if "$PY" "$HERE/$1" "$2"; then :; else rc=1; fi
        echo
    done
    echo "（fix_cdl.py / fix_conb_cdl.py 需要真实网表，无内置样例；"
    echo "  run_with_stack.sh 的检查见 --check stack）"
    return $rc
}

cmd_apply() {
    local id="$1"; shift
    if ! is_valid_id "$id"; then
        echo "未知修复 id：$id（可用：$FIX_IDS）" >&2
        return 2
    fi
    if [ $# -eq 0 ]; then
        echo "用法：./apply_fixes.sh --apply $id $(fix_usage "$id")" >&2
        return 2
    fi
    local s="$HERE/$(fix_script "$id")"
    case "$s" in
        *.py) exec "$PY" "$s" "$@" ;;
        *.sh) exec bash "$s" "$@" ;;
    esac
}

# ---------------------------------------------------------------- 入口

case "${1:-}" in
    --list|-l|"")
        cmd_list ;;
    --show)
        shift
        is_valid_id "${1:-}" || { echo "用法：./apply_fixes.sh --show <id>（可用：$FIX_IDS）" >&2; exit 2; }
        cmd_show "$1" ;;
    --check)
        shift
        cmd_check "$@" ;;
    --selftest)
        cmd_selftest ;;
    --apply)
        shift
        cmd_apply "$@" ;;
    -h|--help)
        sed -n '2,24p' "$0" ;;
    *)
        echo "未知参数：$1" >&2
        echo "用 --list 看可用修复，--help 看用法。" >&2
        exit 2 ;;
esac
