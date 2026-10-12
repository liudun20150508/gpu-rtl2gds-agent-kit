---
name: foundry-handoff
description: 从开源工艺切换到晶圆厂 PDK 与先进节点的对接路径：PDK 四类输入、NDA 合规、tapeout 交付物与 foundry 签核流程（含 SMIC/TSMC 等商业工艺）。
---

# 晶圆厂对接（Foundry Handoff）

本仓库在**可流片的开源工艺**上跑通全流程，但流程本身**工具与工艺无关**。
本技能说明如何把它接到晶圆厂的商业 PDK（SMIC / TSMC 等），以及正式签核阶段要补什么。

## 1. 换工艺 = 换四类输入

流程脚本、约束生成、DFT/ATPG 算法、诊断知识库都**不随工艺变化**。
真正随工艺变化的只有四类输入 —— 这正是把它们做成环境变量的原因：

| PDK 组成 | 开源工艺 | SMIC / TSMC 商业工艺 |
|---------|---------|---------------------|
| 时序/功耗库 | `<platform>/*.lib` | 各 corner 的 `.lib`（CCS/ECSM，含 SI） |
| 几何库 | `.lef` | 各层 `.lef` + tech file |
| 物理验证规则 | KLayout 规则deck | Calibre / ICV rule deck |
| 层映射 / RC | layers map + 提取规则 | StarRC / QRC 的 `.nxtgrd` / `.itf` |

```bash
# 接入点：全部环境变量，无代码改动
export PDK_ROOT=/path/to/foundry/pdk
export SKY130_LIB=$PDK_ROOT/libs/<corner>.lib     # 变量名保留，语义=目标工艺时序库
bash flow/env.sh --check
```

> 变量名叫 `SKY130_LIB` 是历史命名，语义是"**当前目标工艺的时序库**"。
> 换成商业 PDK 只需改值，不改脚本。

## 2. PDK 获取与合规（重要）

- 商业 PDK 是**授权物**：需与晶圆厂/工艺平台签 **NDA** 才能获取；
- **不随本仓库分发**，本仓库只提供接入点（环境变量 + 标准格式约定）；
- 仓库 `.gitignore` 已排除 `pdk/`、`*.lib`、`*.lef`、`*.nxtgrd`、`*.itf`，
  防止误提交授权文件；
- 交接给晶圆厂的数据同样受 NDA 约束，注意交付渠道与留存记录。

## 3. 从开源工艺到先进节点，新增哪些签核项

开源工艺单 corner 即可签核；商业主流与先进节点会新增大量签核维度：

| 维度 | 开源单 corner | 先进节点新增 |
|------|--------------|-------------|
| 时序 | 单库单 corner | 多 corner/mode（MMMC）、OCV/AOCV/POCV 裕量、SI 串扰 |
| 物理验证 | 基础 DRC/LVS | 多重曝光、密度、天线、DFM 全套 |
| 电源 | 静态 IR | 动态 IR/EM（VCD 向量）、di/dt 分析 |
| 等价性 | 综合/APR 前后 | 形式验证 RTL vs 门级全流程 |
| DFT | 裸扫描链 + stuck-at | EDT 压缩、OCC、at-speed、MBIST、boundary scan |

**逐项对应关系**见 `signoff-chain` 技能。

## 4. Tapeout 交付包

交给晶圆厂的最小集合（本仓库 `flow/` 可产出前六项）：

1. 填充后 **GDSII**（mask 数据准备起点）
2. 门级 **Verilog** 网表
3. **CDL / SPICE** 原理图网表（LVS 交叉核对）
4. **SDC** 时序约束
5. **SPEF** 寄生参数
6. STA/DRC/LVS/IREM **签核报告**
7. 引脚 / 凸点坐标（封装对齐）
8. 层映射与 fill 策略说明

## 5. Foundry 侧签核流程（怎么和晶圆厂配合）

```
我方交付 ──▶ 晶圆厂用【自己的 deck + 自己的 PDK 版本】重跑
              ├─ DRC / LVS / 天线 / 密度
              ├─ 时序复核（含 foundry 提供的 corner）
              └─ mask data prep（OPC / 数据膨胀）
           ◀── 反馈违规清单 ──▶ 我方修复 → 重交付（迭代）
           ──▶ 最终 mask tapeout
```

实践要点：

- **同一份 GDS 在两套 deck 下结果不同是正常的**，不要用开源 DRC 的通过数去反驳
  foundry 的违规 —— 要按 foundry 的 deck 修；
- 迭代成本主要来自 mask data prep 的重复，所以**收敛前不要频繁送**；
- 提前索取 foundry 的 **DRC/LVS deck + 运行脚本模板**，把它们的调用方式接进 `flow/`，
  可以让本地预检尽量贴近最终结果。

## 6. 诚实边界

开源链负责"**在可流片工艺上把方法跑通、把算法验证正确**"；
商业链 + 商业 PDK 负责"**正式签核 + 流片**"。
两者读写的是同一套工业标准格式，切换成本 = 替换四类输入 + 补齐先进节点签核项。
不要把开源签核结果宣传为 foundry 签核通过。
