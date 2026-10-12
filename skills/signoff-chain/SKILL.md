---
name: signoff-chain
description: 后端六项签核（STA/DRC/LVS/IREM/LEC/低功耗）的开源做法、商业对应工具与通过判据，以及交给晶圆厂前的交付物清单。提到签核、WNS、DRC count、LVS 匹配、IR drop 时使用。
---

# 签核链（Signoff Chain）

签核 = **用独立工具、独立数据、独立判据复核实现结果**。本技能给出六项签核的开源做法、
每项对应的商业工具、以及"什么算通过"的量化判据。

## 总览

| 签核项 | 开源做法 | 商业对应 | 通过判据（本项目实测） |
|-------|---------|---------|---------------------|
| STA 时序 | OpenSTA + OpenRCX SPEF 反标 | PrimeTime / Tempus | 三方案 WNS +1.13 / +2.29 / +3.06 ns @50MHz，全 MET |
| DRC 设计规则 | KLayout 规则deck | Calibre / ICV | 23 / 23 / 23（含库级豁免，逐条可追） |
| LVS 版图网表一致 | KLayout LVS | Calibre LVS | 器件级 240 类型 / 474k 实例 100% 匹配 |
| IREM 电源完整性 | OpenROAD PSM + 静态 EM | RedHawk / Voltus | VDD worst 0.275 mV、VSS 0.316 mV |
| LEC 逻辑等价 | Yosys `equiv` | Formality / Conformal | 综合前后、APR 前后全通过 |
| 低功耗 | UPF 静态检查清单 | VC LP | 电源域接口无 ISO/LS 缺失 |

## 1. STA（时序签核）

```tcl
read_liberty $LIB ; read_verilog $NETLIST ; link_design $TOP
read_sdc $SDC
read_spef $SPEF              ;# 必须先修负索引，见 pitfalls PIT-* 
set_propagated_clock [all_clocks]
report_checks -path_delay max -format full_clock_expanded
report_worst_slack -max ; report_wns ; report_tns
report_checks -path_delay min          ;# hold 同检
report_clock_skew ; report_clock_min_period
```

要点：

- **必须开 `set_propagated_clock`**，否则用理想时钟会低估 skew；
- setup/hold **双向都要报**，只报 setup 是最常见的签核漏项；
- SPEF 反标前先跑 `flow/fixes/fix_spef_negidx.py`，否则解析直接失败；
- 判据不只看 WNS，还要看 **TNS** 与关键路径归属（路径落在哪个模块 → 决定修法）。

## 2. DRC（设计规则检查）

`make drc` 走 KLayout 规则deck，输出 `6_drc_count.rpt`。三方案均为 23 条，且**全部来自
标准单元库自身的内部规则**（库级豁免），而非用户布线——这是判断"是设计问题还是库问题"的关键。

商业链用 Calibre/ICV 的 foundry deck，规则数与豁免策略完全不同：
**不要把开源 DRC 的 0/23 直接等同于 foundry DRC 通过**，两者 deck 不同源。

## 3. LVS（版图 vs 网表）

器件级比对是本项目的强证据：**240 种器件类型、约 47.4 万个实例 100% 匹配**。
产出 `6_lvs.lvsdb` 与 CDL 网表，两者可交叉核对。

- 网络级 LVS（跨电源域、跨宏的完整网络比对）在单机开源流程中受限，
  需要服务器级 Calibre 才能真正闭合 —— 如实标注，不要宣称已闭合；
- CDL 是**交给晶圆厂交叉核对的关键交付物**，`make do-cdl` 产出。

## 4. IREM（IR drop / 电迁移）

```tcl
set_power_net VDD -voltage 1.1 ; set_ground_net VSS
read_activity_file -format SAIF $SAIF
analyze_power_grid -net VDD
report_ir_drop -net VDD -report_file signoff/ir_drop.rpt
analyze_em -net VDD -report_file signoff/em.rpt
```

- **静态**压降为主：本项目 VDD worst 0.275 mV、VSS 0.316 mV；
- **动态**压降（di/dt）需要 VCD/FSDB 向量，开源链不产出，属商业签核项；
- 高电流热点：KV cache 写端口、HBM PHY 供电、MAC 阵列 —— 电源带需单独加固。

## 5. LEC（逻辑等价）

`Yosys equiv` 覆盖"综合前后"与"APR 前后"两个断点。要点：

- 黑盒 SRAM 在 RTL 与网表中**保持同名同参**，等价性才成立（宏级映射由 LVS 覆盖）；
- `dfflibmap` 重映射触发器时若改变了复位行为，等价性会失败 —— 这是坑，不是工具问题；
- 商业链用 Formality/Conformal，可覆盖更复杂的 retiming/clock gating 场景。

## 6. 低功耗（VCLP）

开源链无 UPF 静态验证工具，采用**检查清单**：

- 电源域接口：isolation cell 是否缺失、level-shifter 电压域配对是否正确；
- 电源开关单元插入合法性（MoE 专家阵列下电场景）；
- 该检查清单见 `flow/openroad/09_vclp.md`。

## 交给晶圆厂前的交付物清单

| 交付物 | 格式 | 用途 |
|-------|------|------|
| 填充后版图 | GDSII | mask 数据准备的起点 |
| 门级网表 | Verilog | 与 LVS 交叉核对 |
| 原理图网表 | CDL / SPICE | 器件级 LVS 输入 |
| 时序约束 | SDC | 晶圆厂复核时序收敛边界 |
| 寄生参数 | SPEF | 时序反标与一致性复核 |
| 签核报告 | STA/DRC/LVS/IREM 报告 | 签核证据链 |
| 引脚/凸点坐标 | 文本/CSV | 封装与 bump map 对齐 |

> ⚠️ 开源链签核 **不能替代 foundry 签核**。foundry 用自己的 deck、自己的 PDK 版本、
> 自己的工具重新跑一遍。本仓库的定位是"**在可流片工艺上把方法与算法验证正确**"，
> 让正式签核阶段的迭代成本降到最低。详见 `foundry-handoff`。
