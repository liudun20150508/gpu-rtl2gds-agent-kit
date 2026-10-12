# OpenClaw 适配

> OpenClaw 是 AI 助手网关（不是编码 CLI），它读取**项目根的 `AGENTS.md`**
> （不读 `CLAUDE.md`），并从 `<workspace>/skills` → `.agents/skills` → `~/.agents/skills`
> 逐级查找技能。`~/.openclaw/` 是它的**家目录/状态目录**，不是项目规则目录。

## 部署

```bash
./install.sh --agent openclaw                  # → <project>/skills/ + <project>/AGENTS.md
./install.sh --agent openclaw --scope global   # → ~/.agents/skills/
```

project 作用域下会创建：

```
<project>/skills/
├── backend-flow/     -> <本仓库>/skills/backend-flow
├── signoff-chain/
├── foundry-handoff/
├── commercial-eda/
└── dft-atpg/
<project>/AGENTS.md   （追加引用段落）
```

注意：部署脚本会检测"目标即本仓库自身"的情况并跳过，避免把仓库自己的 `skills/`
链接到自己。

## 与其它 agent 共存

`.agents/skills` 是 Reasonix 与 OpenClaw 的**共同约定目录**。
若同一项目里两个 agent 都要用，可只部署一份：

```bash
./install.sh --agent reasonix --scope global   # → ~/.agents/skills/，两者共用
```

## 验证

```bash
./install.sh --doctor     # 检查探测结果与部署状态
```

在 OpenClaw 会话里问 "遇到 SPEF 解析失败 STA-1670 怎么处理"，
若回答出 `mem[\-1]` → 改用 `\[-1\]`、且只重跑 `6_report`，说明技能已生效。
