#!/usr/bin/env bash
# =============================================================
# gpu-rtl2gds-agent-kit · 第三方设计下载脚本
#
# 三个脚本的分工（别用混）：
#   ./install-deps.sh     装「工具」 —— yosys / openroad / klayout / iverilog …
#   ./designs/fetch.sh    取「设计」 —— 第三方开源 RTL（本脚本）
#   ./install.sh          部署「agent 层」 —— skills / AGENTS.md 到各 agent
#
# 本仓已自带 designs/tiny-npu（INT8 Transformer 加速器），**不需要下载**。
# 这里取的是 designs/README.md 里点名的第三方设计：它们是独立开源项目，
# 直接搬进本仓会造成版本漂移与许可重复，所以按需下载到忽略目录里。
#
# 用法：
#   ./designs/fetch.sh --list             列出可下载项（体积 / 许可 / 上游）
#   ./designs/fetch.sh --check            检查本地已有哪些 + PDK 是否就绪（默认）
#   ./designs/fetch.sh --fetch vortex     下载指定项
#   ./designs/fetch.sh --fetch all        下载全部
#   ./designs/fetch.sh --dest <目录>      指定下载目录（默认 designs/_third_party）
#   ./designs/fetch.sh --dry-run          只打印将执行的命令，不下载
#
# 下载目录默认落在 designs/_third_party/，已在 .gitignore 中忽略，不会误提交。
# 第三方许可以其自带的 LICENSE / COPYING 为准，优先于本仓的 Apache-2.0。
# =============================================================
set -euo pipefail

KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="check"
DEST=""
ONLY=""
DRY=0
SKY130_LIB_DEFAULT="$HOME/tools/OpenROAD-flow-scripts/flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"

while [ $# -gt 0 ]; do
    case "$1" in
        --list)    MODE="list" ;;
        --check)   MODE="check" ;;
        --fetch)   MODE="fetch"; shift; ONLY="${1:-all}" ;;
        --dest)    shift; DEST="${1:-}" ;;
        --dry-run) DRY=1 ;;
        -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
        *) echo "未知参数: $1（用 --help）" >&2; exit 2 ;;
    esac
    shift
done

[ -n "$DEST" ] || DEST="$KIT_ROOT/designs/_third_party"

# ---------- 可下载项：名称|上游|许可|体积|说明 ----------
ITEMS='
vortex|https://github.com/vortexgpgpu/vortex.git|BSD-3-Clause|约 254MB|多核 RISC-V GPGPU，练时钟树与多核布线拥塞
picorv32|https://github.com/YosysHQ/picorv32.git|ISC|约 1.4MB|RISC-V CPU 核，PIT-003（换工艺必须重综合）的反面教材
'

has() { command -v "$1" >/dev/null 2>&1; }

item_names() {
    echo "$ITEMS" | while IFS='|' read -r n u l s d; do
        [ -n "${n:-}" ] || continue
        echo "$n"
    done
}

item_field() {  # $1=名称 $2=字段序号(2=url 3=许可)
    echo "$ITEMS" | while IFS='|' read -r n u l s d; do
        [ -n "${n:-}" ] || continue
        [ "$n" = "$1" ] || continue
        case "$2" in
            2) echo "$u" ;;
            3) echo "$l" ;;
        esac
    done
}

# ---------- --list ----------
if [ "$MODE" = "list" ]; then
    echo "可下载的第三方设计（将下载到: ${DEST}）"
    echo "----------------------------------------------------------------------------------"
    printf '%-12s %-16s %-10s %s\n' "名称" "许可" "体积" "说明"
    echo "----------------------------------------------------------------------------------"
    echo "$ITEMS" | while IFS='|' read -r n u l s d; do
        [ -n "${n:-}" ] || continue
        printf '%-12s %-16s %-10s %s\n' "$n" "$l" "$s" "$d"
    done
    echo "----------------------------------------------------------------------------------"
    echo "上游地址："
    echo "$ITEMS" | while IFS='|' read -r n u l s d; do
        [ -n "${n:-}" ] || continue
        printf '  %-12s %s\n' "$n" "$u"
    done
    echo "本仓自带的 designs/tiny-npu 无需下载。"
    echo "PDK 不由本脚本下载（授权物 + GB 级），见 ./designs/fetch.sh --check 的提示。"
    exit 0
fi

# ---------- --check ----------
if [ "$MODE" = "check" ]; then
    echo "下载目录: $DEST"
    echo "----------------------------------------------------------------------------------"
    printf '%-12s %-10s %s\n' "名称" "状态" "位置 / 下一步"
    echo "----------------------------------------------------------------------------------"
    echo "$ITEMS" | while IFS='|' read -r n u l s d; do
        [ -n "${n:-}" ] || continue
        if [ -d "$DEST/$n/.git" ]; then
            printf '%-12s %-10s %s\n' "$n" "✓ 已下载" "$DEST/$n"
        else
            printf '%-12s %-10s %s\n' "$n" "✗ 未下载" "→ ./designs/fetch.sh --fetch $n"
        fi
    done
    echo "----------------------------------------------------------------------------------"
    # 自带示例
    if [ -f "$KIT_ROOT/designs/tiny-npu/rtl/top.sv" ]; then
        echo "tiny-npu      ✓ 自带     $KIT_ROOT/designs/tiny-npu/rtl（无需下载）"
    else
        echo "tiny-npu      ✗ 缺失     仓库不完整？designs/tiny-npu/rtl/top.sv 不存在"
    fi
    echo "----------------------------------------------------------------------------------"
    LIB="${SKY130_LIB:-$SKY130_LIB_DEFAULT}"
    if [ -f "$LIB" ]; then
        echo "SKY130 PDK    ✓ 就绪     $LIB"
    else
        echo "SKY130 PDK    ✗ 未就绪   缺 $LIB"
        cat <<'TIP'
    PDK 是授权物、体积达 GB 级，且下载方式与 OpenROAD-flow-scripts 版本绑定，
    本脚本不代下，走官方流程：

      ./install-deps.sh --with-orfs     # 克隆并编译 ORFS（1–3 小时，建议 nohup 后台）
      cd <ORFS> && ./setup.sh           # ORFS 自己的 setup 会准备 PDK

    装好后复核：source flow/env.sh && bash flow/env.sh --check
TIP
    fi
    exit 0
fi

# ---------- --fetch ----------
if [ "$MODE" = "fetch" ]; then
    if ! has git; then
        echo "需要 git，但当前环境找不到。先安装 git 再重试。" >&2
        exit 1
    fi

    if [ "$ONLY" = "all" ]; then
        TARGETS="$(item_names)"
    else
        TARGETS="$ONLY"
    fi

    BAD=0
    for t in $TARGETS; do
        url="$(item_field "$t" 2)"
        if [ -z "$url" ]; then
            echo "未知项: ${t}（用 --list 看可选项）" >&2
            BAD=1
            continue
        fi
        dir="$DEST/$t"
        echo "== ${t}（$(item_field "$t" 3)）=="
        if [ -d "$dir/.git" ]; then
            echo "  已存在，跳过: $dir"
            echo "  要更新：git -C $dir pull --ff-only"
            continue
        fi
        if [ "$DRY" = 1 ]; then
            echo "  （dry-run）git clone --depth 1 $url $dir"
            continue
        fi
        mkdir -p "$DEST"
        echo "  克隆: $url"
        git clone --depth 1 "$url" "$dir"
        echo "  完成: $dir"
        echo "  许可: $(item_field "$t" 3) —— 以上游仓库自带的 LICENSE / COPYING 为准"
    done

    [ "$BAD" = 0 ] || exit 2

    echo "----------------------------------------------------------------------------------"
    echo "下一步：把后端脚本指向下载好的 RTL（不写死路径）"
    echo "  export TINYNPU_RTL=$DEST/vortex      # 换成对应设计的 RTL 根目录"
    echo "  export DESIGN_TOP=<顶层模块名>        # 默认 top"
    echo "  目录结构与用法见 designs/README.md"
    exit 0
fi
