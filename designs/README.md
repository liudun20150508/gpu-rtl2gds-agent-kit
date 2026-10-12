# designs/ — 示例设计（让知识库跑得起来）

这个目录回答一个问题：**规则和脚本都看懂了，拿什么设计去跑一遍？**

`skills/` 告诉你坑在哪、`rules/` 告诉你症状对应什么根因、`flow/` 给你能执行的脚本 —— 但如果没有 RTL，
agent 只能「读知识」不能「用知识」。所以这里放**开箱即用的示例 RTL**，部署完就能走一遍综合 / STA / PnR。

## 一、tiny-npu（随仓，本仓库唯一的 RTL）

Transformer 推理加速器，**INT8 定点**，可综合 SystemVerilog（Xilinx FPGA 目标）。
体量 372 KB / 36 个文件，自研代码，无第三方许可负担。

```
designs/tiny-npu/rtl/
├── top.sv                  顶层：AXI4 从机 + 微码控制 + 计算流水
├── pkg/                    类型与参数
│   ├── npu_pkg.sv            顶层参数（阵列尺寸 / 位宽 / SRAM 深度 / 微码深度）
│   ├── isa_pkg.sv            微码指令编码
│   ├── kv_pkg.sv             KV cache 相关类型
│   └── fixed_pkg.sv          定点数类型与转换
├── bus/                    AXI4 接口
│   ├── axi_types.sv          接口类型定义
│   ├── axi_lite_regs.sv      控制寄存器（AXI4-Lite）
│   ├── axi_dma_rd.sv         读通道 DMA
│   └── axi_dma_wr.sv         写通道 DMA
├── ctrl/                   指令控制
│   ├── ucode_fetch.sv        微码取指
│   ├── ucode_decode.sv       微码译码
│   ├── addr_gen.sv           地址生成
│   ├── scoreboard.sv         依赖记分板
│   └── barrier.sv            同步屏障
├── gemm/                   INT8 脉动阵列
│   ├── systolic_array.sv     脉动阵列
│   ├── pe.sv                 处理单元
│   ├── mac_int8.sv           INT8 MAC
│   ├── gemm_ctrl.sv          阵列控制
│   └── gemm_post.sv          后处理（累加结果读出）
├── mem/                    片上存储
│   ├── banked_sram.sv        多体 SRAM
│   ├── sram_dp.sv            双端口 SRAM
│   └── kv_cache_bank.sv      KV cache bank
└── ops/                    Transformer 算子引擎
    ├── softmax_engine.sv / exp_lut.sv
    ├── layernorm_engine.sv / mean_var_engine.sv
    ├── rmsnorm_engine.sv / rsqrt_lut.sv
    ├── gelu_engine.sv / gelu_lut.sv / silu_lut.sv
    ├── rope_engine.sv
    ├── reduce_max.sv / reduce_sum.sv
    └── vec_engine.sv / recip_lut.sv
```

顶层参数都在 `pkg/npu_pkg.sv`（`top.sv` 的 parameter 列表里可见默认值：阵列 16×16、
INT8 数据 / INT32 累加、AXI 数据 128 bit、SRAM 地址 16 bit、微码深度 1024）。

### 怎么跑

综合入口（先用 yosys 过一遍语法与层次，再接 `flow/openroad/` 的编号 TCL）：

```bash
source flow/env.sh                      # 设好 ORFS_ROOT / SKY130_LIB / TINYNPU_RTL
yosys -p "read_verilog -sv designs/tiny-npu/rtl/pkg/*.sv \
                           designs/tiny-npu/rtl/bus/*.sv \
                           designs/tiny-npu/rtl/ctrl/*.sv \
                           designs/tiny-npu/rtl/gemm/*.sv \
                           designs/tiny-npu/rtl/mem/*.sv \
                           designs/tiny-npu/rtl/ops/*.sv \
                           designs/tiny-npu/rtl/top.sv; \
          hierarchy -check -top top; proc; opt; fsm; opt; memory; opt; techmap; opt"
```

`flow/02_synth_sky130.sh` 里的 `read_verilog -sv` 读的正是这一类文件列表，
按 SKY130 标准单元库映射（含双库策略，见 `rules/pitfalls.yaml` 的 PIT-004）。

> **它是 NPU，不是 GPU。** 这点必须说清楚，否则后端关注点会错。
> NPU 这类负载：瓶颈在 SRAM 排布、脉动阵列的局部拥塞、算子引擎的时序收敛路径；
> GPU（SIMT 多核）这类负载：瓶颈在时钟树、多核布局与全局布线拥塞。
> 两者共用同一条签核链，但**布局约束和优化顺序不同**。见 `skills/backend-flow/SKILL.md`。

## 二、vortex（不随仓，按需 clone）

真正的 **RISC-V GPGPU** —— 本仓库名里的 `gpu` 指向的就是它，也是 `skills/` 里
「多核布局 / 时钟树 / 布线拥塞」那条线的实战对象。

它**不放在本仓库**：这是第三方项目，搬进来会产生版本漂移，也让仓库从知识库变成工程镜像。
从上游取：

```bash
git clone https://github.com/vortexgpgpu/vortex.git
export TINYNPU_RTL=/path/to/vortex/rtl     # 后端脚本据此找 RTL
```

- **许可**：BSD 3-Clause，**以上游仓库自带的 LICENSE 为准**
- **规模**：约 13 MB / 418 个 `.v` `.sv` 文件（上游仓库整体约 254 MB，含工具与产物）
- **为什么值得跑**：它是「开源 GPU 后端」的完整靶子 —— 多核、有缓存层次、面积大，
  能真实触发时钟树偏斜、跨核布线拥塞、大面积 PDN 这几类问题，
  而这些在 tiny-npu 这种小设计上根本暴露不出来

## 三、picorv32（不随仓，按需 clone）

一个 RISC-V CPU 核（**ISC 许可**），在本知识库里承担的是「反面教材」的角色 ——
`rules/pitfalls.yaml` 的 **PIT-003**（Nangate45 学术库网表喂 SKY130 LEF → `ORD-2013 master not found`）
就是拿它验证出来的：

```bash
git clone https://github.com/YosysHQ/picorv32.git
```

它自带的 `COPYING` 是 ISC 许可；**一旦要用，请连同上游许可文件一起保留**。

## 四、接入新设计的约定

后端脚本**不硬编码任何 RTL 路径**，一律走环境变量（`flow/env.sh`）：

| 变量 | 指向 | 默认值 |
| --- | --- | --- |
| `ORFS_ROOT` | OpenROAD-flow-scripts 的 `flow/` 目录 | `$HOME/tools/OpenROAD-flow-scripts/flow` |
| `PDK_ROOT` | PDK 根目录 | 空（按需设） |
| `SKY130_LIB` | SKY130 标准单元 `.lib` | `$ORFS_ROOT/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib` |
| `TINYNPU_RTL` | 待跑设计的 RTL 根 | `designs/tiny-npu/rtl` |
| `DESIGN_TOP` | 顶层模块名 | `top` |
| `NPROC` | 并行度（内存紧张时设 1） | `1` |
| `OPENROAD_EXE` / `YOSYS_EXE` / `KLAYOUT_CMD` | 工具可执行文件 | 自动 `command -v` 探测 |

新设计接入的最小步骤：

1. 把 RTL 放到 `designs/<你的设计>/rtl/`（或 clone 到别处，用 `TINYNPU_RTL` 指过去）
2. 若顶层模块名不是 `top`，设 `export DESIGN_TOP=<模块名>`
3. 按 `flow/openroad/` 的编号顺序跑 TCL（`01_floorplan.tcl` → `08_lec.tcl`），
   中间每一步的判据见 `rules/report_rules.yaml`
4. 卡住了先查 `rules/pitfalls.yaml`，再跑 `make fixes` 做环境自检

**换工艺**（SMIC / TSMC 等商业先进节点）时，改的是 `SKY130_LIB` 指向的库与 PDK，
RTL 本身不动 —— 完整流程见 README §9。
