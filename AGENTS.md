# AGENTS.md — gpu-rtl2gds-agent-kit

本文件是**跨 agent 通用入口**（Codex、Reasonix、OpenClaw 均会读取根目录 `AGENTS.md`；
Claude Code 读取 `CLAUDE.md`，见 `adapters/claude-code/README.md`）。

## 这个仓库是什么

把"**数字后端（RTL2GDS）工程经验**"变成 AI agent 可直接消费的资产：

| 层 | 目录 | 作用 |
|----|------|------|
| 知识库 | `skills/` | 5 个技能：流程运维、签核链、晶圆厂对接、商业 EDA、DFT/ATPG |
| 规则引擎 | `rules/` + `engine/` | 坑库 + 阶段诊断规则 + 负载知识；Python 引擎检索与闭环 |
| 流程本体 | `flow/` | 综合/APR/TCL 阶段脚本/DFT 链/修复模板，全部工艺无关 |
| 示例设计 | `designs/` | tiny-npu（INT8 Transformer 加速器，自研 RTL）开箱即用；vortex / picorv32 只给上游 clone 指引 |
| 适配层 | `adapters/` + `install.sh` | 分发给 Claude Code / Reasonix / Codex / OpenClaw |

**它不是 EDA 引擎**：真正的 RTL2GDS 执行由 Yosys / OpenROAD / OpenSTA / KLayout 完成，
本仓库负责**知识、规则、流程编排与诊断**。

## agent 使用本仓库的正确方式

1. **先看技能**：任务涉及后端流程时，读 `skills/<name>/SKILL.md`；
2. **查坑库**：遇到工具报错，先检索 `rules/pitfalls.yaml`
   （或 `python3 -m engine pitfalls --text "<报错文本>"`）；
3. **用引擎**：`python3 -m engine analyze --stage TIMING --report <报告>` 得到结构化诊断；
4. **跑流程**：`source flow/env.sh` 后按 `flow/README.md` 执行，**不要硬编码路径**；
5. **改知识而不是改代码**：新增经验请改 `rules/*.yaml` 或对应 `SKILL.md`，
   引擎代码不含任何硬编码规则；
6. **要跑真实设计**：用随仓的 `designs/tiny-npu/rtl/`（INT8 Transformer 加速器，36 文件，自研）；
   Vortex GPGPU / picorv32 不随仓，按 `designs/README.md` 从上游 clone ——
   接入自己的设计看同文件的 env.sh 变量表（`TINYNPU_RTL` / `DESIGN_TOP`）。

## 技能索引

| 技能 | 什么时候用 |
|------|-----------|
| `skills/backend-flow/SKILL.md` | 跑全流程、三方案配置、阶段产物、6 个必知坑 |
| `skills/signoff-chain/SKILL.md` | STA/DRC/LVS/IREM/LEC/低功耗六项签核的做法与判据 |
| `skills/foundry-handoff/SKILL.md` | 接晶圆厂 PDK（SMIC/TSMC 等）、NDA、tapeout 交付物 |
| `skills/commercial-eda/SKILL.md` | 与商业 EDA 的逐阶段映射与交接格式 |
| `skills/dft-atpg/SKILL.md` | 扫描插入、ATPG、覆盖率收敛、量产 DFT 升级项 |

## 规则库

- `rules/pitfalls.yaml` — 10 条坑（症状 → 根因 → 修法 → 验证），带 `keywords` 供匹配；
- `rules/report_rules.yaml` — 8 条阶段诊断规则（SYN/APR/TIMING/PV/IREM/LEC/VCLP）；
- `rules/workload_knowledge.yaml` — AI 负载特征（KV cache / MoE / TP-PP / QKV / HBM）
  → 物理设计策略 + 实例级绑定表。

## 环境约定

- **不写死路径**：一切通过 `flow/env.sh` 导出的环境变量
  （`ORFS_ROOT`、`SKY130_LIB`、`PDK_ROOT`、`OPENROAD_EXE`、`YOSYS_EXE`、`KLAYOUT_CMD`）；
- **不提交 PDK**：`.gitignore` 已排除 `pdk/`、`*.lib`、`*.lef`、`*.nxtgrd`、`*.itf`（授权物）；
- **大设计用 `-j1`**：并行会导致 route 阶段 OOM（`Signal 9`）。

## 能力边界（不要越界承诺）

- 开源链负责：**在可流片工艺上把方法跑通、算法验证正确、流程闭环**；
- 商业链负责：**多 corner 时序、SI、动态 IR/EM、UPF 验证、EDT/MBIST、先进节点 DRC**；
- **开源签核 ≠ foundry 签核**：foundry 用自己的 deck 与 PDK 版本重跑，详见 `skills/foundry-handoff`。

## 常用命令

```bash
make install            # 部署知识库到已探测到的 agent
make doctor             # 环境与部署自检
make demo               # 规则引擎跑一次示例报告
make test               # 引擎单元测试
python3 -m engine pitfalls --text "STA-1670"   # 坑库检索
```
