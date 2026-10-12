# 架构

## 分层

```
┌─────────────────────────────────────────────────────────────┐
│ 适配层  adapters/ + install.sh + AGENTS.md                  │
│  把下面的知识分发给 Claude Code / Reasonix / Codex / OpenClaw │
├─────────────────────────────────────────────────────────────┤
│ 知识层  skills/*/SKILL.md                                    │
│  人读得懂、agent 加载得了：流程、判据、边界、坑               │
├─────────────────────────────────────────────────────────────┤
│ 规则层  rules/*.yaml            ← 数据（改知识不改代码）      │
│  engine/*.py                    ← 代码（读 YAML、做推理）     │
│  报告解析 → 规则匹配 → 结构化诊断 → 修复动作 → 闭环迭代       │
├─────────────────────────────────────────────────────────────┤
│ 执行层  flow/（shell + Python + TCL）                        │
│  真正驱动 Yosys / OpenROAD / OpenSTA / KLayout               │
└─────────────────────────────────────────────────────────────┘
```

## 为什么"知识"和"引擎"分开

如果把规则写进 Python，新增一条经验就要改代码、跑测试、发版本；
写成 YAML，**新增经验 = 追加一个块**，人和 agent 都能直接读。

```
rules/*.yaml   人类可读、agent 可直接引用、diff 友好
engine/*.py    只负责"读 + 匹配 + 组织输出"，不含任何具体经验
```

引擎是**纯粹的解释器**：删掉全部 `rules/*.yaml`，引擎仍能启动（只是没规则可匹配）。

## 引擎数据流

```
报告文件 (yosys.log / sta.rpt / drc.rpt)
   │
   ├─ parsers.py        正则抽取结构化指标（wns/tns/area/violations/…）
   │
   ├─ knowledge.py      加载 rules/ 三份 YAML（唯一读文件的地方）
   │
   ├─ diagnose.py       阶段规则匹配 + 坑库命中 → 诊断结论
   │      │
   │      ├─ LLM 通道（openai / ollama，可选）
   │      └─ 规则通道（offline，默认）—— LLM 失败/未配置时自动回退
   │
   ├─ prompts.py        两侧共用的提示词与输出契约
   │
   └─ __main__.py       CLI：analyze / optimize / pitfalls / bind

netlist_bind.py   网表 → 实例清单 → 负载特征匹配 → 实例级 TCL 约束
```

**关键取舍**：LLM 是**增强**不是**依赖**。`--no-llm` 时全链路可用，
结果里标明每条结论来自 `rule:<id>` 还是 `pitfall:<id>` 还是 `llm`，保证可追溯。

## 闭环迭代（`engine optimize`）

```
跑流程 → 解析报告 → 诊断 → 应用修复 → 再跑 → 对比 metrics
   ↑                                              │
   └──────────── 未收敛则继续（可设迭代上限）──────┘
```

每次迭代记录：指标变化、命中的规则、采取的动作。收敛或超限即停止并给出总结。

## 扩展点

| 想加什么 | 改哪里 |
|---------|--------|
| 一条新坑 | `rules/pitfalls.yaml` 追加一个块 |
| 一条新诊断规则 | `rules/report_rules.yaml` |
| 一类新负载特征 | `rules/workload_knowledge.yaml` |
| 一个新阶段的报告格式 | `engine/parsers.py` 加一个解析函数 |
| 一个新阶段 | `flow/openroad/NN_*.tcl` + `report_rules.yaml` 加同 stage |
| 支持一个新 agent | `install.sh` 的 `skills_dir_for` / `agents_md_for` 各加一个分支 |

## 设计边界

- **不打包 EDA 工具**：本仓库管编排与知识，工具由用户按官方方式安装；
- **不分发 PDK**：授权物不入库（`.gitignore` 已排除）；
- **不写死路径**：一切路径经 `flow/env.sh` 注入，全仓可 `grep` 验证；
- **不宣称 foundry 签核**：开源 deck 与 foundry deck 不同源，结论只在开源链内成立。
