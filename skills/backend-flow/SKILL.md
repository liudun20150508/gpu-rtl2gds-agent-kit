---
name: backend-flow
description: 开源工艺 RTL2GDS 全流程运维：三方案（基线/+张量核/+AI负载）的跑法、阶段产物链、签核入口与 6 个已踩实的坑。提到 ORFS、张量核、签核、DRC/LVS、SPEF、AI 负载时使用。
---

# 后端全流程运维（开源工艺，三方案）

本技能是把 **RTL → GDS 全流程**在可流片的开源工艺上跑通的操作手册。目标是让 agent
能在不依赖商业 license 的环境中复现整套后端签核链，并把结果整理成可交给晶圆厂的形式。

> 工艺无关性是本技能的设计前提：流程脚本、约束生成、诊断知识库都不绑定具体 PDK，
> 换工艺 = 替换四类输入（见 `foundry-handoff` 技能）。

## 0. 环境参数化（先做这一步）

本仓库不使用任何个人绝对路径，全部通过环境变量注入：

| 变量 | 含义 | 示例 |
|------|------|------|
| `ORFS_ROOT` | OpenROAD-flow-scripts 的 `flow/` 目录 | `$HOME/tools/OpenROAD-flow-scripts/flow` |
| `SKY130_LIB` | 目标工艺的 `.lib`（时序/功耗库） | `<ORFS_ROOT>/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib` |
| `OPENROAD_EXE` / `YOSYS_EXE` / `KLAYOUT_CMD` | 工具可执行文件 | `$HOME/bin/openroad` 等 |
| `PDK_ROOT` | PDK 根目录 | 由 PDK 安装位置决定 |

启动前自检：

```bash
bash flow/env.sh --check        # 打印解析结果并校验文件是否存在
```

**并行度**：三方案规模下单机 32GB 内存必须 `-j1`，否则 route 阶段会被 OOM kill
（症状是 `Signal 9`，不是工具报错，很容易误判成工具 bug）。

## 1. 三方案配置

三份配置放在 `designs/<platform>/<design>/config.mk`，逐级递进：

| 方案 | 配置目录 | 差异 | WNS @50MHz |
|------|---------|------|-----------|
| ① 基线 | `vortex/` | 张量核关闭，先把可流片全流程走通 | **+1.13 ns** |
| ② +张量核 | `vortex_llm/` | 开 FP8/INT8/2:4 稀疏张量核，门数 281,881 → 315,271（+11.8%） | **+2.29 ns** |
| ③ +AI 负载约束 | `vortex_llm_ai/` | ② 基础上叠加负载特征实例级约束 + 电源网络加倍 | **+3.06 ns** |

跑法：

```bash
cd "$ORFS_ROOT"
gmake DESIGN_CONFIG=./designs/sky130hd/vortex_llm/config.mk \
      OPENROAD_EXE="$OPENROAD_EXE" YOSYS_EXE="$YOSYS_EXE" KLAYOUT_CMD="$KLAYOUT_CMD" -j1
```

> 三方案的价值在于**变量隔离**：①证明流程可跑通，②引入真实算力单元引入复杂度，
> ③证明"负载特征能反过来指导物理实现"。任何一步 WNS 恶化都能立刻定位到是配置问题还是流程问题。

## 2. 阶段产物链

产物落在 `results/<platform>/<design>/base/`，逐级可续跑：

```
1_synth.odb → 2_floorplan.odb → 3_place.odb → 4_cts.odb
            → 5_route.odb → 6_1_fill.odb → 6_report/
```

`6_report/` 是签核起点，产出 `6_final.{gds,v,sdc,spef}`。

**续跑原则**：中途失败时不必从头重跑，删掉失败 stage 的日志与 `.json` 后重入即可
（原因见坑 #2）。

## 3. 签核入口

| 项 | 命令 | 产物 | 判据 |
|----|------|------|------|
| STA | `make sta`（或 `flow/openroad/05_sta_signoff.tcl`） | WNS/TNS/skew | 三方案全 MET @50MHz |
| DRC | `make drc` | `reports/6_drc_count.rpt` | 三方案 23/23/23（含库级豁免） |
| LVS | `make lvs` | `6_lvs.lvsdb` | 器件级 240 类型 / 47.4 万实例 **100% 匹配** |
| CDL | `make do-cdl` | 网表 CDL | 供 LVS 与晶圆厂交叉核对 |
| IREM | `flow/openroad/07_irem.tcl` | `signoff/ir_drop.rpt` | VDD worst 0.275 mV / VSS 0.316 mV |

细则见 `signoff-chain` 技能。

## 4. 六个已踩实的坑（遇到直接按修法处理）

完整四段式（症状/根因/修法/验证）见 `rules/pitfalls.yaml`，此处是要点：

1. **SPEF 解析失败（`STA-1670`）** —— 提取工具把负索引总线名写成 `mem[\-1]`，
   tokenizer 在 bus index 里遇到转义符即报错。修法：用 `flow/fixes/fix_spef_negidx.py`
   重写为 `\[-1\]`，**只重跑 `6_report`**，不必重跑布线/提取。
   注意该脚本 docstring 必须是 raw string（`r"""`），否则 `SyntaxWarning` 走 stderr，
   会让 Tcl 的 `exec` 误判为失败。整个 789MB SPEF 中仅 63 处，修复后 2100 万行全量解析通过。

2. **make 假跳过** —— 失败的 stage 只要日志文件存在，make 就认为该 stage 已完成。
   重跑前**必须**删掉 `logs/.../<stage>.log` 及其 `.json`。

3. **单元库与工艺不匹配（`ORD-2013`）** —— 45nm 学术库网表喂给 130nm 工艺的 LEF 会报
   `LEF master ... not found`。必须用目标工艺库重新综合，不要试图桥接两套库。

4. **DFF legalize 失败** —— 采用**双库策略**：`dffmap` 库给综合映射用，
   `patched` 库给 OpenROAD 用（见坑 #6 的补丁库问题）。

5. **`N_MACROS=0`** —— 综合后 SRAM 已被映射为寄存器阵列，`fakeram` 仅作占位，
   这是预期行为，不是缺陷。

6. **补丁库不能喂给 abc** —— 为绕开 OpenROAD 解析问题打的极简 pin 补丁
   （无电容/无时序表）会让 abc 报 `Table cannot be found`。
   **两库分离**：综合用原始库，补丁库只给 OpenROAD。

## 5. AI 负载版（方案③）的约束怎么下

负载特征 → 物理实现的落点是**实例级绑定**，而不是泛泛的全局约束：

| 负载特征 | 绑定的模块族 | 物理策略 |
|---------|-------------|---------|
| KV cache / LMEM | cache data/tags/mshr、local_mem | 宏贴近 LSU/AGU；双 bank 错开读写端口；未命中 bank 关时钟 |
| QKV GEMM 数据通路 | fpu/fma/alu/wallace_mul | 数据通路直通布局；retiming 平衡流水级；skew < 30 ps |
| MoE all-to-all | xbar/switch/arbiter | 等距布局、路由链均衡；总线加 shield；专家阵列可下电 |
| 张量并行 / HBM | axi/membus/kmU | 接口宏固定 die 边缘；控制器与 PHY co-placement；独立电源域 |

方案③实际落地的两条约束：

- `constraint.sdc`：`qkv_datapath` 分组 `group_path -weight 2.0`（覆盖 FMA/FPU/Wallace 乘法器输出 pin）；
- `pdn.tcl`：metal4/metal5 电源带 pitch `27.1 → 13.6 µm`（电源网络加倍）。

约束生成器：`python3 -m engine.netlist_bind <netlist.v> <out.tcl>` —— 读网表模块名，
命中负载特征后生成实例级 TCL 片段。

> 开源工具缺 `set_instance_region` / `set_shielded_net` 这类商业专有命令时，
> 用 `group_path`（SDC 层）+ PDN 加倍**语义等价替代**，并在报告中如实标注替代关系。

## 6. 本技能不覆盖什么

- 多 corner/MMMC、OCV/AOCV/POCV、SI 签核 —— 开源单 corner 流程不产出这些；
- 动态 IR/EM（需 VCD/FSDP 向量）；
- 测试压缩、at-speed、MBIST —— 见 `dft-atpg` 技能的量产升级清单。

这些是**商业签核项**，衔接方式见 `commercial-eda` 与 `foundry-handoff`。
