#!/usr/bin/env bash
# =============================================================
# gpu-rtl2gds-agent-kit · 开源 EDA 工具链安装脚本
#
# 分工：本脚本只装**跑流程要用的工具**。
#   部署 agent 层（skills / AGENTS.md） → ./install.sh
#   下载第三方设计（vortex / picorv32） → ./designs/fetch.sh
#   一键串起三步                       → ./deploy.sh
#
# 工具分三档，按需装：
#   core    python3 + PyYAML（规则引擎必需）、iverilog（仿真 → 波形）
#   signoff yosys（综合）、klayout（DRC/LVS/版图渲染）、openroad（APR/STA/IREM）
#   extra   verilator（更快的仿真）、gtkwave（波形 GUI，可选）
#
# 用法：
#   ./install-deps.sh --check        只检查，不安装（默认）
#   ./install-deps.sh --install      按平台安装缺失的工具
#   ./install-deps.sh --dry-run      只打印将执行的命令，不动系统
#   ./install-deps.sh --tier core    只处理 core 档
#   ./install-deps.sh --with-orfs    额外克隆 OpenROAD-flow-scripts（编译命令见文末）
#
# 说明：知识库与规则引擎（engine/）只依赖 core 档；装不上 EDA 工具也不影响使用。
# =============================================================
set -euo pipefail

MODE="check"        # check | install
TIER="all"          # core | signoff | all
DRY=0
WITH_ORFS=0

while [ $# -gt 0 ]; do
    case "$1" in
        --check)      MODE="check" ;;
        --install)    MODE="install" ;;
        --dry-run)    DRY=1; MODE="install" ;;
        --with-orfs)  WITH_ORFS=1 ;;
        --tier)       shift; TIER="${1:-all}" ;;
        -h|--help)    sed -n '2,23p' "$0"; exit 0 ;;
        *) echo "未知参数: $1（用 --help）" >&2; exit 2 ;;
    esac
    shift
done

# ---------- 平台探测 ----------
detect_platform() {
    case "$(uname -s)" in
        Darwin) echo "macos" ;;
        Linux)
            if [ -r /etc/os-release ]; then
                # shellcheck disable=SC1091
                . /etc/os-release
                case "${ID:-}${ID_LIKE:-}" in
                    *debian*|*ubuntu*) echo "debian" ;;
                    *rhel*|*fedora*|*centos*) echo "rhel" ;;
                    *) echo "linux-other" ;;
                esac
            else
                echo "linux-other"
            fi ;;
        *) echo "unknown" ;;
    esac
}
PLATFORM="$(detect_platform)"

# ---------- 工具表：名字 档位 用途 平台包名 验证命令 ----------
# 包名里的 @cask: 前缀 = Homebrew cask（不是 formula），展开成 `--cask <名>`
# 空包名（-）= 发行版里没有，见文末「照着敲」的命令
# 用普通函数代替关联数组，兼容 macOS 自带的 bash 3.2
TOOLS="python3 core 规则引擎解释器 python3 python3
iverilog core 仿真出VCD（波形） icarus-verilog iverilog
verilator extra 更快的仿真 verilator verilator
yosys signoff 逻辑综合 yosys yosys
klayout signoff DRC/LVS/版图渲染 @cask:klayout klayout
openroad signoff APR/STA/IREM - openroad
gtkwave extra 波形GUI查看器 @cask:gtkwave gtkwave"

pkg_of() {  # $1=tool  $2=档位内的包名（macos 用主名，debian/rhel 见下）
    local tool="$1" mac="$2"
    case "$PLATFORM" in
        macos) echo "$mac" ;;
        debian)
            case "$tool" in
                python3)  echo "python3 python3-pip python3-yaml" ;;
                iverilog) echo "iverilog" ;;
                verilator) echo "verilator" ;;
                yosys)    echo "yosys" ;;
                klayout)  echo "" ;;      # Ubuntu 官方源无 klayout，用 flatpak 或官网 .deb
                openroad) echo "" ;;      # 无发行版包
                gtkwave)  echo "gtkwave" ;;
                *)        echo "" ;;
            esac ;;
        rhel)
            case "$tool" in
                python3)  echo "python3 python3-pip python3-pyyaml" ;;
                iverilog) echo "iverilog" ;;
                verilator) echo "verilator" ;;
                yosys)    echo "yosys" ;;
                klayout|openroad) echo "" ;;
                gtkwave)  echo "gtkwave" ;;
                *)        echo "" ;;
            esac ;;
        *) echo "" ;;
    esac
}

installer_cmd() {
    case "$PLATFORM" in
        macos) echo "brew install" ;;
        debian) echo "sudo apt-get install -y" ;;
        rhel) echo "sudo dnf install -y" ;;
        *) echo "" ;;
    esac
}

expand_pkgs() {  # @cask:klayout -> --cask klayout（其余原样）
    local out="" p
    for p in $1; do
        case "$p" in
            @cask:*) out="$out --cask ${p#@cask:}" ;;
            *)       out="$out $p" ;;
        esac
    done
    echo "${out# }"
}

manual_hint() {  # 无发行版包的工具 → 一行可执行提示
    local tool="$1"
    case "$PLATFORM:$tool" in
        *:openroad)
            echo "装不上包 → ./install-deps.sh --with-orfs 自建，或 Docker openroad/orfs（见文末①）" ;;
        debian:klayout|rhel:klayout|linux-other:klayout)
            echo "flatpak install flathub de.klayout.klayout（或官网 .deb，见文末②）" ;;
        macos:klayout)
            echo "brew install --cask klayout" ;;
        *)
            echo "无发行版包，需手动安装（见文末）" ;;
    esac
}

want_tier() {  # $1=工具档位，判断当前 TIER 是否包含它
    case "$TIER" in
        all) return 0 ;;
        core) [ "$1" = "core" ] ;;
        signoff) [ "$1" = "core" ] || [ "$1" = "signoff" ] ;;
        *) return 0 ;;
    esac
}

has() { command -v "$1" >/dev/null 2>&1; }

# ---------- 主流程 ----------
echo "平台: $PLATFORM"
echo "档位: $TIER   模式: $MODE$([ "$DRY" = 1 ] && echo '（dry-run）')"
echo "----------------------------------------------------------------------"
printf '%-12s %-8s %-26s %s\n' "工具" "档位" "用途" "状态"
echo "----------------------------------------------------------------------"

echo "$TOOLS" | while read -r tool tier use mac_pkg verify; do
    [ -n "${tool:-}" ] || continue
    want_tier "$tier" || continue
    if has "$verify"; then
        printf '%-12s %-8s %-26s %s\n' "$tool" "$tier" "$use" "✓ 已装"
    else
        pkg="$(pkg_of "$tool" "$mac_pkg")"
        if [ -n "$pkg" ]; then
            printf '%-12s %-8s %-26s %s\n' "$tool" "$tier" "$use" "✗ 缺失 → $(installer_cmd) $(expand_pkgs "$pkg")"
        else
            printf '%-12s %-8s %-26s %s\n' "$tool" "$tier" "$use" "✗ 缺失 → $(manual_hint "$tool")"
        fi
    fi
done

# python 包：PyYAML
echo "----------------------------------------------------------------------"
if python3 -c 'import yaml' >/dev/null 2>&1; then
    echo "PyYAML        ✓ 已装（规则引擎读 rules/*.yaml 需要）"
    YAML_OK=1
else
    echo "PyYAML        ✗ 缺失 → python3 -m pip install --user pyyaml"
    YAML_OK=0
fi

# ---------- 收集缺失项（重新遍历，便于安装） ----------
needs_install=""
echo "$TOOLS" | while read -r tool tier use mac_pkg verify; do
    [ -n "${tool:-}" ] || continue
    want_tier "$tier" || continue
    has "$verify" && continue
    pkg="$(pkg_of "$tool" "$mac_pkg")"
    [ -n "$pkg" ] && echo "$pkg"
done > /tmp/rtl2gds_deps_pkgs.$$ 2>/dev/null || true

if [ -f "/tmp/rtl2gds_deps_pkgs.$$" ]; then
    needs_install="$(sort -u "/tmp/rtl2gds_deps_pkgs.$$" | tr '\n' ' ')"
    rm -f "/tmp/rtl2gds_deps_pkgs.$$"
fi

# ---------- 安装 ----------
if [ "$MODE" = "install" ]; then
    echo "----------------------------------------------------------------------"
    cmd="$(installer_cmd)"
    if [ -n "$needs_install" ] && [ -n "$cmd" ]; then
        echo "将执行: $cmd $(expand_pkgs "$needs_install")"
        if [ "$DRY" = 1 ]; then
            echo "（dry-run，未执行）"
        else
            # shellcheck disable=SC2086
            $cmd $(expand_pkgs "$needs_install")
        fi
    elif [ -z "$needs_install" ]; then
        echo "发行版包已齐，无需安装。"
    else
        echo "当前平台没有可用的包管理器，请手动安装下列工具：$needs_install"
    fi

    if [ "$YAML_OK" = 0 ]; then
        if [ "$DRY" = 1 ]; then
            echo "将执行: python3 -m pip install --user pyyaml"
        else
            python3 -m pip install --user pyyaml
        fi
    fi
fi

# ---------- 无发行版包的工具：照着敲这些命令 ----------
cat <<'TIP'
----------------------------------------------------------------------
① openroad（APR/STA/IREM）—— 发行版里没有，三选一

   自建（推荐：与 flow/ 的脚本、env.tcl 完全对齐，编译约 1–3 小时）
       ./install-deps.sh --with-orfs                    # 本脚本负责克隆
       cd ~/tools/OpenROAD-flow-scripts
       ./setup.sh && ./build_openroad.sh --local        # 编译（建议 nohup 后台）
       export ORFS_ROOT=~/tools/OpenROAD-flow-scripts/flow

   Docker（不想装编译环境）
       docker pull openroad/orfs:latest
       docker run -it --rm -v "$PWD:/work" openroad/orfs:latest

   Ubuntu 预编译包（版本号以 release 页为准）
       # 从 https://github.com/The-OpenROAD-Project/OpenROAD/releases 取对应 Ubuntu 版本的 .deb
       sudo apt install ./openroad_<版本>_amd64-ubuntu<22.04|24.04>.deb

② klayout（DRC/LVS/版图渲染）

   macOS : brew install --cask klayout          # 注意是 cask，不是 formula
   Ubuntu: flatpak install flathub de.klayout.klayout
           或从官网下载 .deb：https://www.klayout.de/build.html
   RHEL  : flatpak install flathub de.klayout.klayout

③ 装完统一自检

   ./install-deps.sh --check        # 工具是否齐
   ./install.sh --doctor            # agent 层是否就位
   make demo                        # 规则引擎是否可用

PyYAML 装不上时：引擎对 YAML 的读取是唯一硬依赖，
没它 engine/ 与 make demo 无法运行，必须先解决。
----------------------------------------------------------------------
TIP

# ---------- OpenROAD-flow-scripts 克隆（可选，编译交给你决定） ----------
if [ "$WITH_ORFS" = 1 ]; then
    echo "== OpenROAD-flow-scripts =="
    target="${ORFS_ROOT:-$HOME/tools/OpenROAD-flow-scripts}"
    if [ -d "$target" ]; then
        echo "已存在: ${target}（跳过克隆）"
    else
        echo "将克隆到: $target"
        if [ "$DRY" = 1 ]; then
            echo "（dry-run，未执行）"
        else
            mkdir -p "$(dirname "$target")"
            git clone --recurse-submodules https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts.git "$target"
        fi
    fi
    echo "接下来（耗时长，建议 nohup 丢后台）："
    echo "  cd $target && ./setup.sh && ./build_openroad.sh --local"
    echo "编译完成后设置："
    echo "  export ORFS_ROOT=$target/flow"
    echo "自检："
    echo "  source flow/env.sh && bash flow/env.sh --check"
fi

echo "----------------------------------------------------------------------"
echo "提示：装完后跑 ./install.sh --doctor 检查 agent 层部署状态，"
echo "      用 make demo 验证规则引擎可用。"
