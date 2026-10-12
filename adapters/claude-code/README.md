# Claude Code 适配

## 技能发现

Claude Code 从项目的 `.claude/skills/<name>/SKILL.md` 读取技能（AgentSkills 规范）。

```bash
./install.sh --agent claude-code              # 部署到当前项目 .claude/skills/
./install.sh --agent claude-code --scope global   # 或 ~/.claude/skills/
```

部署后目录形如：

```
<project>/.claude/skills/
├── backend-flow/SKILL.md      -> <本仓库>/skills/backend-flow
├── signoff-chain/SKILL.md     -> ...
├── foundry-handoff/SKILL.md
├── commercial-eda/SKILL.md
└── dft-atpg/SKILL.md
```

默认软链接，`git pull` 本仓库后技能即时更新；要固化用 `--copy`。

## 项目说明文件

Claude Code 读 `CLAUDE.md` 而非 `AGENTS.md`。把本仓库的 `adapters/claude-code/CLAUDE.md`
复制到你的项目根（或追加到已有 `CLAUDE.md`）：

```bash
cp <本仓库>/adapters/claude-code/CLAUDE.md <your-project>/CLAUDE.md
```

## 验证

在 Claude Code 里问一句 "跑后端流程前要检查哪些环境变量"，
若回答提到 `ORFS_ROOT` / `SKY130_LIB`，说明 `backend-flow` 技能已被加载。
