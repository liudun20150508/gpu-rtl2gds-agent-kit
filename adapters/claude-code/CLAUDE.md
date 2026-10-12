# Claude Code 项目说明模板 —— gpu-rtl2gds-agent-kit
#
# 用法：复制到你的业务项目根目录作为 CLAUDE.md，或追加到已有 CLAUDE.md 末尾。
# 把 <KIT> 替换为本仓库的实际绝对路径。

## 数字后端（RTL2GDS）知识库

本项目涉及芯片后端流程时，优先使用 gpu-rtl2gds-agent-kit 的知识库，不要凭通用经验自己写后端约束。

- 知识库根目录：`<KIT>`
- 技能（先读）：`<KIT>/skills/<name>/SKILL.md`
  - `backend-flow` 全流程与三方案配置、6 个必知坑
  - `signoff-chain` STA/DRC/LVS/IREM/LEC 六项签核的做法与判据
  - `foundry-handoff` 接晶圆厂 PDK（SMIC/TSMC 等）、NDA、tapeout 交付物
  - `commercial-eda` 与商业 EDA 的逐阶段映射与交接格式
  - `dft-atpg` 扫描插入、ATPG、覆盖率收敛
- 坑库：`<KIT>/rules/pitfalls.yaml`（10 条，症状 → 根因 → 修法 → 验证）
- 规则引擎：`python3 -m engine pitfalls --text "<报错文本>"`
  / `python3 -m engine analyze --stage TIMING --report <报告>`
- 流程脚本：`source <KIT>/flow/env.sh` 后按 `<KIT>/flow/README.md` 执行

## 硬性约定

1. **不写死路径**：工具与库位置一律走 `flow/env.sh` 导出的环境变量
   （`ORFS_ROOT`、`SKY130_LIB`、`PDK_ROOT`、`OPENROAD_EXE`、`YOSYS_EXE`、`KLAYOUT_CMD`）。
2. **不提交 PDK**：`*.lib` / `*.lef` / `*.nxtgrd` / `*.itf` 是授权物，禁止入库。
3. **大设计用 `-j1`**：并行会让 route 阶段 OOM（`Signal 9`）。
4. **改知识而不是改代码**：新增经验写进 `rules/*.yaml` 或 `SKILL.md`，引擎代码不硬编码规则。

## 能力边界

- 开源链：把方法跑通、算法验证正确、流程闭环；
- 商业链：多 corner 时序、SI、动态 IR/EM、UPF 验证、EDT/MBIST、先进节点 DRC；
- **开源签核 ≠ foundry 签核**，不要宣称开源 DRC/LVS 通过等同于晶圆厂签核通过。
