# Codex 适配

## 说明文件

Codex 读取 **`AGENTS.md`**（agents.md 约定）。本仓库根目录已有 `AGENTS.md`，
部署脚本会把它写入你的项目根（带标记块，便于卸载）：

```bash
./install.sh --agent codex              # → <project>/AGENTS.md
./install.sh --agent codex --scope global   # → ~/.codex/AGENTS.md
```

写入的是**引用段落**而非全文复制，包含：

- 技能位置 `<本仓库>/skills/<name>/SKILL.md`
- 坑库与检索命令
- 引擎入口 `make demo`
- 流程脚本 `source flow/env.sh`

## 技能

Codex 没有 `.claude/skills` 那样的项目技能目录约定，
本仓库的技能通过 `AGENTS.md` 段落里的**路径引用**暴露给 Codex：
agent 需要时会直接读 `<本仓库>/skills/<name>/SKILL.md`。

若你的 Codex 版本支持 skills 目录，可额外执行：

```bash
./install.sh --agent claude-code --target <your-project>   # 装进 .claude/skills 供复用
```

## 验证

在 Codex 里问 "后端签核链包括哪几项、判据是什么"，
若回答提到 DRC 23/23/23、LVS 240 类型 47.4 万实例 100% 匹配等具体数字，
说明 `signoff-chain` 技能已被读取。
