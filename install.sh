#!/bin/bash
# =============================================================
# rtl2gds-agent-kit · 部署脚本
#
# 把本仓库的知识库（skills/ + AGENTS.md）分发给本机已安装的 AI agent：
#   Claude Code  → <target>/.claude/skills/     （或 ~/.claude/skills）
#   Reasonix     → <target>/.reasonix/skills/   （或 ~/.agents/skills）
#   Codex        → <target>/AGENTS.md           （或 ~/.codex/AGENTS.md）
#   OpenClaw     → <target>/skills/ + AGENTS.md （或 ~/.agents/skills）
#
# 用法：
#   ./install.sh                        # 自动探测，部署到当前目录（project 作用域）
#   ./install.sh --agent claude-code    # 只部署给指定 agent
#   ./install.sh --scope global         # 部署到各 agent 的全局目录
#   ./install.sh --target /path/to/proj # 部署到指定项目
#   ./install.sh --copy                 # 复制而非软链接（默认软链接）
#   ./install.sh --doctor               # 只做环境与部署自检
#   ./install.sh --uninstall            # 卸载
#
# 软链接模式：agent 读的是本仓库实时内容，git pull 即更新。
# 若移动/删除本仓库，请重新部署。
# =============================================================
set -uo pipefail

KIT_ROOT="$(cd "$(dirname "$0")" && pwd)"
SKILLS_SRC="$KIT_ROOT/skills"
AGENTS_MD="$KIT_ROOT/AGENTS.md"
MARK_BEGIN="# >>> rtl2gds-agent-kit >>>"
MARK_END="# <<< rtl2gds-agent-kit <<<"

SCOPE="project"
TARGET="$PWD"
MODE="link"
AGENT="auto"
ACTION="install"

usage() {
    sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --agent)     AGENT="${2:-auto}"; shift 2 ;;
        --scope)     SCOPE="${2:-project}"; shift 2 ;;
        --target)    TARGET="${2:-$PWD}"; shift 2 ;;
        --copy)      MODE="copy"; shift ;;
        --link)      MODE="link"; shift ;;
        --uninstall) ACTION="uninstall"; shift ;;
        --doctor)    ACTION="doctor"; shift ;;
        -h|--help)   usage; exit 0 ;;
        *) echo "未知参数: $1" >&2; usage; exit 2 ;;
    esac
done

case "$SCOPE" in project|global) ;; *) echo "--scope 只能是 project 或 global" >&2; exit 2 ;; esac
[ -d "$SKILLS_SRC" ] || { echo "找不到 $SKILLS_SRC" >&2; exit 1; }

# ---- skill 列表 ----
skill_names() { ls -1 "$SKILLS_SRC" 2>/dev/null; }

# ---- 各 agent 的技能目录（echo 输出父目录；空 = 该 agent 不用 skills 目录）----
skills_dir_for() {
    local agent="$1"
    if [ "$SCOPE" = "global" ]; then
        case "$agent" in
            claude-code) echo "$HOME/.claude/skills" ;;
            reasonix)    echo "$HOME/.agents/skills" ;;
            openclaw)    echo "$HOME/.agents/skills" ;;
            codex)       echo "" ;;
        esac
    else
        case "$agent" in
            claude-code) echo "$TARGET/.claude/skills" ;;
            reasonix)    echo "$TARGET/.reasonix/skills" ;;
            openclaw)    echo "$TARGET/skills" ;;
            codex)       echo "" ;;
        esac
    fi
}

# ---- 各 agent 的 AGENTS.md 位置（空 = 不在该作用域写）----
agents_md_for() {
    local agent="$1"
    if [ "$SCOPE" = "global" ]; then
        case "$agent" in codex) echo "$HOME/.codex/AGENTS.md" ;; *) echo "" ;; esac
    else
        case "$agent" in
            codex|reasonix|openclaw) echo "$TARGET/AGENTS.md" ;;
            *) echo "" ;;
        esac
    fi
}

# ---- agent 探测 ----
detect_agent() {
    case "$1" in
        claude-code) command -v claude >/dev/null 2>&1 || [ -d "$HOME/.claude" ] ;;
        reasonix)    command -v reasonix >/dev/null 2>&1 || [ -d "$HOME/.reasonix" ] \
                        || [ -f "$TARGET/reasonix.toml" ] ;;
        codex)       command -v codex >/dev/null 2>&1 || [ -d "$HOME/.codex" ] ;;
        openclaw)    command -v openclaw >/dev/null 2>&1 || [ -d "$HOME/.openclaw" ] ;;
        *) return 1 ;;
    esac
}

resolve_agents() {
    if [ "$AGENT" = "auto" ]; then
        local found=""
        for a in claude-code reasonix codex openclaw; do
            detect_agent "$a" && found="$found $a"
        done
        [ -n "$found" ] || found=" codex"   # 全都没探测到：至少部署 AGENTS.md
        echo $found
    elif [ "$AGENT" = "all" ]; then
        echo "claude-code reasonix codex openclaw"
    else
        echo "$AGENT"
    fi
}

# ---- 部署一个 agent ----
deploy_agent() {
    local agent="$1" dir md n=0
    dir="$(skills_dir_for "$agent")"
    md="$(agents_md_for "$agent")"

    if [ -n "$dir" ]; then
        # 防呆：目标即本仓库自身时跳过
        if [ "$(cd "$KIT_ROOT" && pwd)" = "$(cd "$dir/../.." 2>/dev/null && pwd || echo x)" ] \
           && [ "$agent" = "openclaw" ]; then
            echo "  [$agent] 跳过（目标即本仓库自身）"
        else
            mkdir -p "$dir"
            for s in $(skill_names); do
                if [ "$MODE" = "copy" ]; then
                    rm -rf "$dir/$s"; cp -R "$SKILLS_SRC/$s" "$dir/$s"
                else
                    ln -sfn "$SKILLS_SRC/$s" "$dir/$s"
                fi
                n=$((n + 1))
            done
            echo "  [$agent] $n 个技能 → $dir ($MODE)"
        fi
    else
        echo "  [$agent] 无 skills 目录约定，依赖 AGENTS.md"
    fi

    if [ -n "$md" ]; then
        mkdir -p "$(dirname "$md")"
        if [ -f "$md" ] && grep -qF "$MARK_BEGIN" "$md" 2>/dev/null; then
            echo "  [$agent] AGENTS.md 已含本仓库段落，跳过"
        else
            {
                echo ""
                echo "$MARK_BEGIN"
                echo "## 数字后端（RTL2GDS）知识库"
                echo ""
                echo "本项目的后端流程、签核与 DFT 任务请先读："
                echo "- 技能：\`$KIT_ROOT/skills/<name>/SKILL.md\`"
                echo "- 坑库：\`$KIT_ROOT/rules/pitfalls.yaml\`（检索：\`python3 -m engine pitfalls --text \"<报错>\"\`）"
                echo "- 引擎：\`cd $KIT_ROOT && make demo\`"
                echo "- 流程：\`source $KIT_ROOT/flow/env.sh\` 后按 \`$KIT_ROOT/flow/README.md\` 执行"
                echo ""
                echo "在业务仓库里优先用 RTL2GDS 知识库的结论，不要凭通用经验改写后端约束。"
                echo "$MARK_END"
            } >> "$md"
            echo "  [$agent] 已写入 $md"
        fi
    fi
}

# ---- 卸载 ----
uninstall_agent() {
    local agent="$1" dir md
    dir="$(skills_dir_for "$agent")"
    md="$(agents_md_for "$agent")"
    if [ -n "$dir" ] && [ -d "$dir" ]; then
        for s in $(skill_names); do
            if [ -L "$dir/$s" ]; then rm -f "$dir/$s"; elif [ -d "$dir/$s" ]; then rm -rf "$dir/$s"; fi
        done
        echo "  [$agent] 已移除 $dir 下的技能"
    fi
    if [ -n "$md" ] && [ -f "$md" ] && grep -qF "$MARK_BEGIN" "$md" 2>/dev/null; then
        python3 - "$md" "$MARK_BEGIN" "$MARK_END" <<'PY'
import os
import sys
path, b, e = sys.argv[1], sys.argv[2], sys.argv[3]
lines, out, skip = open(path, encoding="utf-8").read().splitlines(True), [], False
for ln in lines:
    if b in ln: skip = True
    if not skip: out.append(ln)
    if e in ln: skip = False
tail = "".join(out).rstrip()
if tail:
    open(path, "w", encoding="utf-8").write(tail + "\n")
else:
    os.remove(path)
PY
        echo "  [$agent] 已从 $md 移除本仓库段落"
    fi
}

# ---- 自检 ----
doctor() {
    echo "== rtl2gds-agent-kit 自检 =="
    echo "仓库: $KIT_ROOT"
    echo "技能: $(skill_names | wc -l | tr -d ' ') 个 → $(skill_names | tr '\n' ' ')"
    echo "规则: $(ls -1 "$KIT_ROOT/rules" 2>/dev/null | wc -l | tr -d ' ') 个文件"
    echo ""
    echo "== agent 探测 =="
    for a in claude-code reasonix codex openclaw; do
        if detect_agent "$a"; then echo "  [已装] $a"; else echo "  [未探测到] $a"; fi
    done
    echo ""
    echo "== 依赖 =="
    command -v python3 >/dev/null 2>&1 && echo "  [OK] python3 $(python3 -V 2>&1 | awk '{print $2}')" \
        || echo "  [MISS] python3（规则引擎必需）"
    python3 -c 'import yaml' >/dev/null 2>&1 && echo "  [OK] PyYAML" \
        || echo "  [MISS] PyYAML（pip install pyyaml）"
    for t in openroad yosys klayout; do
        command -v "$t" >/dev/null 2>&1 && echo "  [OK] $t" || echo "  [可选未装] $t"
    done
    echo ""
    echo "== 部署状态（当前目录）=="
    for d in .claude/skills .reasonix/skills .agents/skills skills; do
        [ -d "$d" ] && echo "  [有] $d: $(ls -1 "$d" 2>/dev/null | tr '\n' ' ')"
    done
    [ -f AGENTS.md ] && echo "  [有] AGENTS.md"
    echo ""
    echo "下一步：cd $KIT_ROOT && make test   验证引擎可用"
}

# ---- 主流程 ----
AGENTS_LIST="$(resolve_agents)"

case "$ACTION" in
    doctor)    doctor ;;
    uninstall) echo "卸载（scope=${SCOPE}）："; for a in $AGENTS_LIST; do uninstall_agent "$a"; done ;;
    install)
        echo "部署 rtl2gds-agent-kit（scope=${SCOPE}, mode=${MODE}）"
        echo "  agent: $AGENTS_LIST"
        [ "$SCOPE" = "project" ] && echo "  目标: $TARGET"
        for a in $AGENTS_LIST; do
            case "$a" in claude-code|reasonix|codex|openclaw) deploy_agent "$a" ;;
                         *) echo "  未知 agent: $a" >&2 ;; esac
        done
        echo ""
        echo "完成。自检：$0 --doctor"
        echo "Reasonix 用户也可在 reasonix.toml 里直接指向："
        echo "  [skills]"
        echo "  paths = [\"$KIT_ROOT/skills\"]"
        ;;
esac
