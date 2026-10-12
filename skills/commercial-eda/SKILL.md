---
name: commercial-eda
description: 开源后端流程与商业 EDA 的逐阶段对应与交接方式：综合/APR/时序/物理验证/IREM/LEC 的工具映射、标准交换格式与任意阶段交接点。
---

# 衔接商业 EDA 工具链

开源链与商业链读写的是**同一套工业标准交换格式**，所以交接是"换工具"，不是"重写流程"。
本技能给出逐阶段映射与交接点。

## 1. 逐阶段工具映射

| 阶段 | 本仓库（开源） | 商业对应 | 交接格式 | 交接方式 |
|------|--------------|---------|---------|---------|
| 综合 SYN | Yosys（`abc -D` 约束驱动） | Design Compiler / Fusion Compiler | 门级网表 + SDC | 商业工具直接 `read` 开源网表重跑综合 |
| 布局布线 APR | OpenROAD（floorplan→place→CTS→route） | ICC2 / Innovus | DEF / Verilog | 读入 DEF 继续；或换工具重跑同网表 |
| 时序 STA | OpenSTA + OpenRCX SPEF | PrimeTime / Tempus | SDC + SPEF | 商业工具做**最终 signoff** |
| 物理验证 PV | KLayout（DRC/LVS） | Calibre / ICV | GDSII + 网表 + CDL | 换 deck 重跑，规则集由 foundry 提供 |
| 电源 IREM | OpenROAD PSM + 静态 EM | RedHawk / Voltus | DEF + SPEF + SAIF/VCD | 商业工具补动态分析 |
| 等价性 LEC | Yosys `equiv` | Formality / Conformal | RTL + 网表 | 商业工具覆盖 retiming/clock gating |
| 低功耗 | 检查清单 | VC LP | UPF | 需补写 UPF 描述 |
| DFT | 自研 SCAN/ATPG | Tessent / TetraMAX | 网表 + 测试协议 | 算法层可复用，引擎换商业 |

## 2. 为什么能交接：格式统一

| 数据 | 格式 | 谁读 |
|------|------|------|
| 门级网表 | Verilog | 所有综合/APR/PV 工具 |
| 时序约束 | SDC（Tcl） | STA / APR / 综合 |
| 物理库 | LEF | APR / PV |
| 布局结果 | DEF | APR |
| 寄生参数 | SPEF / DSPF | STA |
| 版图 | GDSII | PV / tapeout |
| 标准单元时序 | Liberty（`.lib`） | 综合 / STA |

**没有任何私有格式参与交接** —— 这是"开源验证方法 + 商业正式签核"这条路线成立的根本原因。

## 3. 常见的"开源做不了、商业能做"清单

不要承诺开源链能做这些：

- 多 corner/mode 统一收敛（MMMC）、OCV/AOCV/POCV 裕量
- 信号完整性（SI / crosstalk）签核
- 动态 IR/EM（需要向量激励）
- 商业专有命令：`set_instance_region`、`set_shielded_net` 等
  → 本项目用 `group_path`（SDC）+ PDN 加倍做**语义等价替代**，并在报告中标注
- UPF 静态低功耗验证（VC LP 级）
- 测试压缩（EDT）、at-speed、MBIST
- 先进节点 DRC（多重曝光/密度/DFM）

## 4. 建议的交接策略

1. **开源链跑到"方法正确"**：流程闭环、算法验证、约束生成器可用；
2. **留给商业链的是"签核与收敛"**：把开源产物当输入，而不是把开源工具当替代品；
3. **把 foundry deck 接进 `flow/`**：提前对齐调用方式，减少正式签核迭代轮次；
4. **报告里如实标注工具归属**：哪项用开源完成、哪项待商业签核，一目了然。
