# Reasonix 适配

## 技能发现

Reasonix 按优先级发现技能：**项目目录 > `[skills].paths` 自定义 > 全局 > 内置**。
项目内可识别的技能目录包括 `.reasonix/`、`.agents/`、`.agent/`、`.claude/` 下的 `skills/`，
布局为 `<name>/SKILL.md` 或扁平 `<name>.md`。

本仓库的技能是标准的 `<name>/SKILL.md`，因此**两种接法都行**：

### 接法 A：软链接进项目（推荐，与其它 agent 共用）

```bash
./install.sh --agent reasonix            # → <project>/.reasonix/skills/
./install.sh --agent claude-code         # → <project>/.claude/skills/（Reasonix 也认这个目录）
```

### 接法 B：直接指向本仓库（改 reasonix.toml）

```toml
[skills]
paths = ["/absolute/path/to/rtl2gds-agent-kit/skills"]
```

好处：技能与仓库同生命周期，`git pull` 即更新，无需重新部署。

## 项目说明文件

Reasonix 会加载 `REASONIX.md` / `AGENTS.md` / `CLAUDE.md`。
本仓库根目录已有 `AGENTS.md`；若你的业务项目另有说明，建议在本仓库 `AGENTS.md` 里追加一段
指向业务项目的约定，或在业务项目里引用：

```markdown
## 后端流程
见 rtl2gds-agent-kit（路径：/absolute/path/to/rtl2gds-agent-kit）。
```

## 与规则引擎配合

Reasonix 可直接调用引擎（无需网络）：

```bash
cd /path/to/rtl2gds-agent-kit && make demo        # 规则引擎跑示例报告
python3 -m engine pitfalls --text "STA-1670"      # 坑库检索
```

在 agent 会话里让 Reasonix 执行上述命令，即可把结构化诊断引入对话。
