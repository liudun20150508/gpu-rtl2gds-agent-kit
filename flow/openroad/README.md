# OpenROAD RTL2GDS 流程 (Linux 服务器执行)

本目录是覆盖数字后端全流程的脚本集。
macOS 无法运行 OpenROAD,本套脚本在 Linux (Ubuntu 22.04 + OpenROAD-flow-scripts 环境) 上执行。

## 流程映射 (后端阶段 <-> 本流程)

| 后端阶段 | 商业工具 | 本流程开源等价 | 脚本 |
|-----------|---------------------|---------------|------|
| SYN       | Design Compiler / Fusion Compiler | Yosys (已完成,本机) | ../02_synth.sh |
| APR       | ICC2 / Innovus | OpenROAD (floorplan→place→CTS→route) | 01_floorplan.tcl ~ 05_route.tcl |
| TIMING    | PrimeTime | OpenSTA | 06_sta_signoff.tcl |
| PV        | Calibre / ICV | Magic/Klayout DRC/LVS | 07_pv_drc_lvs.tcl |
| IREM      | RedHawk / Voltus | OpenROAD PSM (IR) + 静态 EM 分析 | 08_irem.tcl |
| LEC       | Formality / Conformal | Yosys equiv_opt / LEC | 09_lec.tcl |
| VCLP      | VC LP | UPF 仿真 + 手工检查清单 | 10_vclp.md |

## 执行

```bash
# 1. 综合(本机已跑通, 输出 gate 网表)
bash ../02_synth.sh

# 2. 后端物理实现 (Linux + OpenROAD)
cd flow/openroad
./run_all.sh <design.v> <NangateOpenCellLibrary.lef> <typical.lib>
```
