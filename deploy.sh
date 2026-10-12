#!/usr/bin/env bash
# =============================================================
# gpu-rtl2gds-agent-kit · 一键部署
#
# 把三个分工脚本串成一条链，每一步都带自检，失败就停下：
#
#   ① 工具链    ./install-deps.sh    python3 / PyYAML / yosys / klayout / openroad …
#   ② 示例设计  ./designs/fetch.sh   vortex、picorv32（默认只自检，不下载）
#   ③ agent 层  ./install.sh         skills + AGENTS.md → Claude Code / Reasonix / Codex / OpenClaw
#
# 用法：
#   ./deploy.sh                    交互式：每一步问一次（默认）
#   ./deploy.sh --yes              全程不提问，适合 CI 或一键装
#   ./deploy.sh --check            只自检，不装任何东西
#   ./deploy.sh --dry-run          只打印将执行的命令，不动系统
#   ./deploy.sh --only deps        只跑其中一步（deps | designs | agent）
#   ./deploy.sh --agent codex      指定 agent（默认 auto：自动探测本机装了什么）
#   ./deploy.sh --scope global     部署范围 project（默认，装到当前项目）或 global
#   ./deploy.sh --with-designs     连第三方设计一起下载（vortex 约 254MB，默认跳过）
#   ./deploy.sh -h | --help        本帮助
#
# 每一步失败都会停下并说明原因，不会默默继续。
# 知识库与规则引擎只依赖 core 档工具：装不上 EDA 工具也能用 make demo。
# =============================================================
set -euo pipefail

KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODE="run"          # run | check
DRY=0
YES=0
ONLY=""
AGENT="auto"
SCOPE="project"
WITH_DESIGNS=0

while [ $# -gt 0 ]; do
    case "$1" in
        --yes|-y)        YES=1 ;;
        --check)         MODE="check" ;;
        --dry-run)       DRY=1 ;;
        --only)          shift; ONLY="${1:-}" ;;
        --agent)         shift; AGENT="${1:-auto}" ;;
        --scope)         shift; SCOPE="${1:-project}" ;;
        --with-designs)  WITH_DESIGNS=1 ;;
        -h|--help)       sed -n '2,26p' "$0"; exit 0 ;;
        *) echo "未知参数: $1（用 --help）" >&2; exit 2 ;;
    esac
    shift
done

case "$ONLY" in
    ""|deps|designs|agent) ;;
    *) echo "未知阶段: ${ONLY}（可选 deps | designs | agent）" >&2; exit 2 ;;
esac

# ---------- 输出小工具 ----------
section() { echo ""; echo "======================================================"; echo "$1"; echo "======================================================"; }
ok()      { echo "  ✓ $1"; }
warn()    { echo "  ! $1"; }

run() {   # 会改变系统的命令：dry-run 时只打印
    if [ "$DRY" = 1 ]; then
        echo "  （dry-run）$*"
        return 0
    fi
    "$@"
}

show() {  # 只读命令：dry-run 时照样执行
    "$@"
}

confirm() {  # $1=问题；--yes 直接过；非交互环境（无 TTY）不擅自确认
    if [ "$YES" = 1 ]; then return 0; fi
    if [ ! -t 0 ]; then
        warn "非交互环境，跳过需确认的步骤（要全自动请加 --yes）"
        return 1
    fi
    printf '  %s [y/N] ' "$1"
    read -r ans || ans=""
    case "$ans" in [yY]*) return 0 ;; *) return 1 ;; esac
}

step_wanted() {  # $1=阶段名
    [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]
}

# =============================================================
section "gpu-rtl2gds-agent-kit 一键部署"
echo "  仓库: $KIT_ROOT"
echo "  agent: $AGENT    scope: $SCOPE"
echo "  模式: $MODE$([ "$DRY" = 1 ] && echo '（dry-run）')$([ "$YES" = 1 ] && echo '（不提问）')"

# ---------- ① 工具链 ----------
if step_wanted deps; then
    section "① 开源 EDA 工具链"
    show bash "$KIT_ROOT/install-deps.sh" --tier all --check

    if [ "$MODE" = "check" ]; then
        ok "工具链自检完成（--check 模式不安装）"
    elif confirm "要把缺失的工具装上吗？（会调用 brew / apt-get / dnf / pip）"; then
        if run bash "$KIT_ROOT/install-deps.sh" --install; then
            ok "工具链安装步骤结束，重新自检："
            show bash "$KIT_ROOT/install-deps.sh" --check
        else
            warn "工具安装未成功 —— 知识库与规则引擎只依赖 core 档，可继续；"
            warn "缺 openroad / klayout 时先看 install-deps.sh 文末的「照着敲」命令。"
        fi
    else
        warn "已跳过工具安装（core 档以外不影响 make demo）"
    fi
fi

# ---------- ② 示例设计 ----------
if step_wanted designs; then
    section "② 示例设计"
    if [ "$WITH_DESIGNS" = 1 ]; then
        if [ "$MODE" = "check" ]; then
            ok "跳过下载（--check 模式），当前状态："
            show bash "$KIT_ROOT/designs/fetch.sh" --check
        elif confirm "下载第三方设计 vortex + picorv32？（约 255MB）"; then
            if run bash "$KIT_ROOT/designs/fetch.sh" --fetch all; then
                ok "第三方设计已就绪"
            else
                warn "下载失败 —— 不影响知识库使用，可稍后重跑 ./designs/fetch.sh --fetch all"
            fi
        else
            warn "已跳过第三方设计下载"
        fi
    else
        show bash "$KIT_ROOT/designs/fetch.sh" --check
        ok "designs/tiny-npu 随仓自带，开箱即用（要第三方设计请加 --with-designs）"
    fi
fi

# ---------- ③ agent 层 ----------
if step_wanted agent; then
    section "③ agent 层（skills + AGENTS.md）"
    if [ "$MODE" = "check" ]; then
        show bash "$KIT_ROOT/install.sh" --doctor
        ok "agent 层自检完成（--check 模式不部署）"
    else
        if run bash "$KIT_ROOT/install.sh" --agent "$AGENT" --scope "$SCOPE"; then
            ok "agent 层部署完成，复查："
            show bash "$KIT_ROOT/install.sh" --doctor
        else
            warn "agent 层部署未完成 —— 可单独重试："
            warn "  ./install.sh --agent $AGENT --scope $SCOPE"
        fi
    fi
fi

# ---------- 收尾 ----------
section "完成"
echo "  下一步："
echo "    make test        引擎单元测试"
echo "    make demo        用示例报告跑一次规则引擎"
echo "    make fixes       流程修复脚本自检"
echo "    make fetch       第三方设计状态"
echo ""
echo "  真跑流程前设好环境变量（脚本不硬编码路径）："
echo "    source flow/env.sh && bash flow/env.sh --check"
echo ""
echo "  目录结构与用法：README.md、designs/README.md"
echo "======================================================"
