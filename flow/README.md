# flow/ — 流程脚本与 TCL

本目录是**可执行的流程本体**：从 RTL 到 GDS 的每一步、六项签核、以及 DFM/DFT 辅助脚本。
所有脚本**工艺无关**，靠环境变量接入具体 PDK（见 `flow/env.sh`）。

## 0. 先载入环境

```bash
source flow/env.sh          # 载入默认值 + 你的覆盖
bash   flow/env.sh --check  # 自检：打印解析结果并校验路径是否存在
```

| 变量 | 含义 | 默认 |
|------|------|------|
| `ORFS_ROOT` | OpenROAD-flow-scripts 的 `flow/` 目录 | `~/tools/OpenROAD-flow-scripts/flow` |
| `SKY130_LIB` | 目标工艺时序库 `.lib`（历史命名，语义=目标工艺库） | `$ORFS_ROOT/platforms/sky130hd/lib/...tt_025C_1v80.lib` |
| `PDK_ROOT` | 商业 PDK 根目录（换 SMIC/TSMC 时设置） | 空 |
| `OPENROAD_EXE` / `YOSYS_EXE` / `KLAYOUT_CMD` | 工具可执行文件 | 自动 `command -v` |
| `TINYNPU_RTL` | 示例设计 RTL 目录 | `$PWD/tiny-npu` |
| `NPROC` | 并行度 | `1`（大型设计必须串行，否则 route 阶段 OOM） |

## 1. 顶层脚本

| 脚本 | 作用 |
|------|------|
| `env.sh` | 环境参数化 + 自检（`--check` / `--export`） |
| `01_prep_sources.sh` | 源码准备：SystemVerilog → 综合可读形式 |
| `02_synth.sh` | 综合（通用路径） |
| `02_synth_sky130.sh` | 综合（SKY130 专用：`abc -D` 约束驱动 + 双库策略） |
| `03_sta.sh` | 时序分析入口 |
| `extract_metrics.py` | 从报告/日志抽取结构化指标 |
| `render_gds.py` | GDS 渲染（出图/检查） |
| `make_floorplan_gds.py` | 生成 floorplan 视图 |
| `make_cell_layout.py` | 单元素版图视图 |
| `make_schematic.py` | 网表→原理图视图 |

## 2. `openroad/` — 阶段 TCL

九步流水，每步一个 TCL，可单独执行也可 `run_all.sh` 串跑：

```
01_floorplan.tcl → 02_place.tcl → 03_cts.tcl → 04_route.tcl
05_sta_signoff.tcl  06_pv.tcl  07_irem.tcl  08_lec.tcl
09_vclp.md（检查清单，无对应工具）
```

| 文件 | 作用 |
|------|------|
| `env.tcl` | Tcl 侧环境（读 `$::env(ORFS_ROOT)` 等，不写死路径） |
| `inst_bind.tcl` | 负载特征 → 实例级约束（由 `engine.netlist_bind` 生成） |
| `lvs.tcl` | LVS 调用 |
| `run_all.sh` | 顺序跑全部阶段 |

详见 `openroad/README.md`。

## 3. `dft/` — 可测性设计链

```
01_synth.sh → 02_scan_insert.py → 03_atpg.py → 04_pattern_verify.py
```

| 文件 | 作用 |
|------|------|
| `01_synth.sh` | 综合 + 门级网表 |
| `02_scan_insert.py` | mux-D 扫描插入、链均衡、观测点插入 |
| `03_atpg.py` | 自研 ATPG：并行故障模拟 + PODEM + 逐模式精确检测集 |
| `04_pattern_verify.py` | 门级仿真 vs 参考机交叉比对 |
| `dbg_*.py` / `run_dbg_shift.sh` | 调试脚本（链路/参考机/移位/TAP） |

方法、覆盖率收敛数据与量产升级项见 `skills/dft-atpg/SKILL.md`。

## 4. `fixes/` — 修复模板

| 文件 | 作用 |
|------|------|
| `fix_spef_negidx.py` | 修 SPEF 负索引 `mem[\-1]`（STA-1670）。**docstring 必须是 raw string**，否则 `SyntaxWarning` 走 stderr 会让 Tcl `exec` 误判失败 |
| `TIMING_fix.txt` | 时序修复记录（由 `engine diagnose` 追加） |

## 5. 跑之前要知道的四件事

1. **重跑前必须删日志**：make 以日志存在判断 stage 完成，失败也会留日志 → 假跳过。
2. **`-j1`**：大设计并行会让 route 阶段 `Signal 9`（OOM），不是工具 bug。
3. **详细布线栈溢出**：`ulimit -s 65536` 后重跑。
4. **SPEF 先修再反标**：见 `fixes/fix_spef_negidx.py`。

完整坑库（10 条，含症状/根因/修法/验证）见 `rules/pitfalls.yaml`，
可用 `python3 -m engine pitfalls --text "<报错文本>"` 检索。
