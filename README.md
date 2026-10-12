# gpu-rtl2gds-agent-kit

> **把数字后端（RTL2GDS）的工程经验，做成 AI agent 可以直接用的知识库。**
>
> 一套可部署的**后端知识库 + 规则引擎 + 流程/TCL 脚本**，适配 Claude Code / Reasonix /
> Codex / OpenClaw，让 agent 在没有商业 license 的环境中也能把 RTL → GDS 全流程跑通、
> 把六项签核做完整、把结果整理成可以交给晶圆厂的形式。

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

---

## 1. 这个仓库要解决什么问题

数字后端工程的核心难点**不是工具怎么点，而是经验怎么传**：

| 痛点 | 现实 | 本仓库的做法 |
|------|------|-------------|
| **坑重复踩** | 同一个 `STA-1670`、同一个栈溢出，每个人都要再栽一次 | `rules/pitfalls.yaml`：症状 → 根因 → 修法 → 验证，四段式沉淀，可检索 |
| **诊断靠人** | 报告几百行，定位根因依赖资深工程师 | `engine/`：报告解析 → 规则匹配 → 结构化诊断与修复动作，离线可用 |
| **AI 不懂后端** | 通用 LLM 会写出错误的后端约束（"把频率降一半就行"） | `skills/`：把流程、签核判据、能力边界写成 agent 可消费的技能文件 |
| **经验锁在个人机器上** | 脚本里写死绝对路径，换台机器就跑不动 | 全部路径走 `flow/env.sh` 环境变量，换 PDK 零代码改动 |

**一句话定位**：本仓库**不是 EDA 引擎**。真正的综合、布局布线、签核由
Yosys / OpenROAD / OpenSTA / KLayout 完成；本仓库负责**知识、规则、流程编排与诊断**。

---

## 2. 目录结构

```
gpu-rtl2gds-agent-kit/
├── AGENTS.md              # 跨 agent 通用入口（Codex/Reasonix/OpenClaw 读取）
├── install.sh             # 一键部署到各 agent（探测/部署/自检/卸载）
├── Makefile               # make install / doctor / demo / test
│
├── skills/                # ① 知识库（AgentSkills 规范，agent 自动加载）
│   ├── backend-flow/      #    全流程运维、三方案配置、6 个必知坑
│   ├── signoff-chain/     #    六项签核的做法、判据与交付物
│   ├── foundry-handoff/   #    接晶圆厂 PDK、NDA、tapeout 交付
│   ├── commercial-eda/    #    与商业 EDA 的逐阶段映射
│   └── dft-atpg/          #    扫描插入、ATPG、覆盖率收敛
│
├── rules/                 # ② 规则引擎的数据层（纯 YAML，改知识不改代码）
│   ├── pitfalls.yaml            # 10 条坑：症状/根因/修法/验证 + keywords
│   ├── report_rules.yaml        # 8 条阶段诊断规则（SYN/APR/TIMING/PV/IREM/LEC/VCLP）
│   └── workload_knowledge.yaml  # AI 负载特征 → 物理设计策略 + 实例绑定表
│
├── engine/                # ③ 规则引擎（Python，零网络依赖可跑）
│   ├── knowledge.py       #    唯一读 YAML 的地方
│   ├── diagnose.py        #    LLM → 规则引擎回退链；闭环迭代
│   ├── netlist_bind.py    #    网表 → 负载特征 → 实例级 TCL 约束
│   ├── parsers.py         #    报告解析（yosys / OpenSTA / OpenROAD）
│   └── __main__.py        #    CLI：analyze / optimize / pitfalls / bind
│
├── flow/                  # ④ 流程本体（35 个脚本，全部工艺无关）
│   ├── env.sh             #    环境参数化 + 自检
│   ├── 01_prep_sources.sh … 03_sta.sh
│   ├── openroad/          #    9 个阶段 TCL（floorplan→route→签核）
│   ├── dft/               #    综合→扫描插入→ATPG→模式验证
│   ├── plot_timing.py     #    时序指标 CSV → 时序 SVG（零依赖）
│   ├── plot_waveform.py   #    VCD → 波形 SVG（零依赖）
│   ├── render_gds.py / make_floorplan_gds.py / make_cell_layout.py
│   │                      #    GDS/DEF/LEF → 版图视图
│   ├── make_schematic.py  #    门级网表 → 逻辑设计图/原理图
│   └── fixes/             #    修复模板（SPEF 负索引等）
│
├── adapters/              # ⑤ 各 agent 的接法文档
├── examples/              # ⑥ 示例数据（时序 CSV、扫描链 testbench 与 VCD）
├── docs/                  # ⑦ 架构文档 + figures/（版图·原理图·时序·波形 四类图）
└── tests/                 # 引擎单元测试（14 个用例）
```

---

## 3. 快速开始（3 步）

```bash
git clone <this-repo> gpu-rtl2gds-agent-kit
cd gpu-rtl2gds-agent-kit

make doctor     # ① 环境自检：agent 探测 + 依赖检查 + 部署状态
make test       # ② 验证规则引擎可用（14 个用例）
make install    # ③ 部署知识库到你机器上已安装的 agent
```

`make install` 会自动探测本机装了哪些 agent 并分发；也可以精确指定：

```bash
make install AGENT=claude-code            # 只部署给 Claude Code
make install AGENT=all SCOPE=global       # 部署到四家的全局目录
make uninstall
```

**不需要 EDA 工具也能验证仓库可用**：`make demo` 用内置示例报告跑一次完整诊断。

### 单独用规则引擎（不依赖任何 agent）

```bash
pip install pyyaml

python3 -m engine pitfalls --text "read_spef failed: STA-1670"     # 坑库检索
python3 -m engine analyze --stage TIMING --report <sta报告> --no-llm # 报告诊断
python3 -m engine bind design.v flow/openroad/inst_bind.tcl         # 生成实例级约束
python3 -m engine optimize --stage TIMING --run "make sta" --reports wns.rpt
```

---

## 4. 部署到 AI agent

| Agent | 读取的说明文件 | 技能目录 | 部署命令 |
|-------|--------------|---------|---------|
| **Claude Code** | `CLAUDE.md` | `.claude/skills/` | `make install AGENT=claude-code` |
| **Reasonix** | `AGENTS.md` / `REASONIX.md` | `.reasonix/skills/`、`.agents/skills/` | `make install AGENT=reasonix` |
| **Codex** | `AGENTS.md` | 经 `AGENTS.md` 引用 | `make install AGENT=codex` |
| **OpenClaw** | `AGENTS.md` | `<workspace>/skills/` | `make install AGENT=openclaw` |

设计要点：

- **技能格式跨 agent 通用**：`AGENTS.md`（agents.md 约定）+ `skills/<name>/SKILL.md`
  （AgentSkills 约定）是当前覆盖面最广的两个约定，一套源文件四家共用；
- **默认软链接**：`git pull` 本仓库后 agent 立即看到最新知识（要固化用 `--copy`）；
- **AGENTS.md 用标记块追加**：不覆盖你项目已有的说明，卸载时干净移除；
- **Reasonix 也可以直接指过来**，无需部署：

  ```toml
  [skills]
  paths = ["/absolute/path/to/gpu-rtl2gds-agent-kit/skills"]
  ```

细节见 `adapters/<agent>/README.md`。

---

## 5. 知识库：5 个技能

agent 会在相关任务上自动加载；人也可以直接读。

| 技能 | 内容 | 什么时候用 |
|------|------|-----------|
| [`backend-flow`](skills/backend-flow/SKILL.md) | 环境参数化、三方案配置、阶段产物链、6 个必知坑、AI 负载约束怎么下 | 跑全流程 |
| [`signoff-chain`](skills/signoff-chain/SKILL.md) | 六项签核的开源做法 + 商业对应 + 量化判据 + 晶圆厂交付物 | 做签核 |
| [`foundry-handoff`](skills/foundry-handoff/SKILL.md) | PDK 四类输入、NDA 合规、tapeout 交付包、foundry 侧签核流程 | 对接晶圆厂 |
| [`commercial-eda`](skills/commercial-eda/SKILL.md) | 逐阶段工具映射、标准交换格式、交接策略 | 接商业工具 |
| [`dft-atpg`](skills/dft-atpg/SKILL.md) | 扫描插入、自研 ATPG、覆盖率收敛、量产升级项 | 做 DFT |

---

## 6. 流程与 TCL 脚本

`flow/` 是**可执行的流程本体**，全部工艺无关 —— 换工艺只改环境变量。

```bash
source flow/env.sh          # 载入参数
bash   flow/env.sh --check  # 自检：打印解析结果并校验路径
```

| 变量 | 含义 |
|------|------|
| `ORFS_ROOT` | OpenROAD-flow-scripts 的 `flow/` 目录 |
| `SKY130_LIB` | 目标工艺时序库（历史命名，语义 = **当前目标工艺的库**） |
| `PDK_ROOT` | 商业 PDK 根目录（换 SMIC/TSMC 时设置） |
| `OPENROAD_EXE` / `YOSYS_EXE` / `KLAYOUT_CMD` | 工具可执行文件 |
| `NPROC` | 并行度（大设计必须 `1`，否则 route 阶段 OOM） |

### 阶段 TCL（`flow/openroad/`）

| TCL | 阶段 | 干什么 |
|-----|------|--------|
| `01_floorplan.tcl` | 布局规划 | 读 LEF/DEF、宏摆放、电源网络、die 尺寸 |
| `02_place.tcl` | 布局 | 全局/详细布局、合法化、时序驱动 |
| `03_cts.tcl` | 时钟树 | 建树、平衡 skew、插入 buffer |
| `04_route.tcl` | 布线 | 全局/详细布线、修 DRC、填充 |
| `05_sta_signoff.tcl` | 时序签核 | 反标 SPEF、setup/hold 双向检查、skew |
| `06_pv.tcl` | 物理验证 | DRC / LVS / CDL |
| `07_irem.tcl` | 电源完整性 | 静态 IR drop + EM |
| `08_lec.tcl` | 等价性 | 综合前后、APR 前后 |
| `09_vclp.md` | 低功耗 | 检查清单（开源无对应工具） |

辅助：`env.tcl`（Tcl 侧环境，读 `$::env(...)` 不写死路径）、
`inst_bind.tcl`（由引擎生成的实例级约束）、`lvs.tcl`、`run_all.sh`。

画图脚本：`plot_timing.py`（时序指标 → 时序 SVG）、`plot_waveform.py`（VCD → 波形 SVG）、
`render_gds.py` / `make_floorplan_gds.py` / `make_cell_layout.py`（版图）、
`make_schematic.py`（逻辑设计图）—— 见本章末「画图脚本」小节。

### 跑流程前必须知道的四件事

1. **重跑前删日志**：make 以日志存在判断 stage 完成，失败也留日志 → 假跳过；
2. **`-j1`**：并行会让 route 阶段 `Signal 9`（OOM），不是工具 bug；
3. **详细布线栈溢出**：`ulimit -s 65536` 后重跑；
4. **SPEF 先修再反标**：`flow/fixes/fix_spef_negidx.py` 修负索引，只重跑 `6_report`。

完整 10 条坑见 [`rules/pitfalls.yaml`](rules/pitfalls.yaml)。

---

### 画图脚本：版图 / 逻辑设计图 / 时序 / 波形

后端交付物不只有文本报告——图是签核与复盘的证据。本仓库自带画图脚本，其中时序与波形两个是**零第三方依赖**的纯 Python 实现，直接产出 SVG（浏览器和 GitHub 都能看，不需要 gtkwave / matplotlib）：

| 脚本 | 输入 | 输出 |
| --- | --- | --- |
| `flow/plot_timing.py` | 时序指标 CSV（`name,wns_ns,tns_ns,freq_mhz,gates,violations`） | 时序图 SVG：WNS 裕量条形图（带 0 基线，负值自动标红）+ 门数规模条形图 |
| `flow/plot_waveform.py` | 仿真 VCD | 波形图 SVG：单 bit 阶梯波形（0/1 蓝线，x/z 灰线）、多 bit 总线十六进制取值、时间网格刻度 |
| `flow/render_gds.py`、`flow/make_floorplan_gds.py`、`flow/make_cell_layout.py` | GDS / DEF / LEF | 版图视图（全芯片、floorplan、单元级） |
| `flow/make_schematic.py` | 门级网表 | 逻辑设计图 / 原理图 |

> 版图与原理图脚本依赖具体 EDA 工具（KLayout 等），依赖与参数见各脚本头部注释。

**示例产物**（本仓库已生成，可直接点开看）：

- **版图**：[全芯片版图](docs/figures/layout/chip_full.png) · [版图总览](docs/figures/layout/chip_layout.png) · [标准单元版图](docs/figures/layout/sky130_cells_layout.png) · [单元 CMOS 截面](docs/figures/layout/cell_nand2_cmos.png)
- **逻辑设计图**：[门级原理图](docs/figures/schematic/gates_schematic.png) · [ALU 门级](docs/figures/schematic/alu_gates_rtl.png) · [仲裁器原理图](docs/figures/schematic/rr_arbiter.png)
- **时序**：[三方案时序裕量与规模对比](docs/figures/timing/three_variants.svg)
- **波形**：[扫描链移位与捕获时序](docs/figures/waveform/scan_shift.svg)

**一键复现时序与波形图**（波形走真实仿真，不是画出来的示意图）：

```bash
# 时序图：CSV → SVG
python3 flow/plot_timing.py examples/timing/three_variants.csv \
    -o docs/figures/timing/three_variants.svg --title "三方案时序裕量与规模对比"

# 波形图：iverilog 仿真 → VCD → SVG
cd examples/waveforms
iverilog -o /tmp/scan_chain.vvp scan_chain_tb.v && vvp /tmp/scan_chain.vvp
python3 ../../flow/plot_waveform.py scan_shift.vcd -o scan_shift.svg \
    --title "扫描链移位与捕获时序" --signals clk,scan_en,scan_in,scan_out,d,q
```

`examples/waveforms/scan_chain_tb.v` 是一个最小 4 位扫描链：`scan_en=0` 并行捕获、`scan_en=1` 移位串出，波形里能直接看到链尾依次移出 `A→5→B→6→C→8→0→A`。换成自己的设计时，替换 RTL 与 testbench 并保留 `$dumpvars` 即可。

> 这些版图/原理图示例取自开源工艺 SKY130 上的实际实现，用于说明**产物格式与判读方式**；换到商业工艺时图的类型与看点不变，只是换成 Virtuoso / ICC2 / Innovus 的对应视图。

### 修复脚本（`flow/fixes/`）

流程挂掉时**能直接执行的修法**收在这里，不再只是文档里的一段说明。总入口：

```bash
make fixes                                        # 列出全部修复 + 环境自检
make fixes-list                                   # 只列清单
./flow/fixes/apply_fixes.sh --show  <id>          # 看某条的症状、根因、用法
./flow/fixes/apply_fixes.sh --check <id> <参数>    # 只诊断，不改任何文件
./flow/fixes/apply_fixes.sh --apply <id> <参数>    # 应用
```

| id | 修什么 | 触发症状 |
|---|---|---|
| `spef` | SPEF 负索引毒 token | STA `read_spef` 报 `[ERROR STA-1670] syntax error` |
| `cdl` | CDL 实例行缺单元名 | LVS 读不进网表 / 器件数对不上 |
| `conb` | conb tie cell 与版图提取不一致 | LVS 卡在 `sky130_fd_sc_hd__conb_*` |
| `dfflib` | 生成 dffmap / patched 两份 lib | 综合报 `$_DFFE_PP_ cannot be legalized` |
| `stack` | 抬高栈上限跑布线 | detail route Signal 11 / `boost::polygon::MaxCover` |

每个 id 都与 `rules/pitfalls.yaml` 里的坑条目一一对应：**坑库负责「知道该怎么做」，脚本负责「不用每次手敲」**。
agent 读到报错 → 匹配坑 → 直接调脚本改掉 → 重跑验证，中间不必回头问人。

其中 `dfflib`（双库策略）与 `stack`（栈上限）在原项目里只有文字描述、没有脚本，这里是补上的；
`cdl` / `conb` 两个 LVS 前置清理原本散落在别处。各条的细节与坑中坑见 [`flow/fixes/README.md`](flow/fixes/README.md)。

## 7. 签核链：六项，各自的判据

| 签核项 | 开源做法 | 商业对应 | 通过判据（本仓库实测） |
|-------|---------|---------|---------------------|
| **STA 时序** | OpenSTA + OpenRCX SPEF 反标 | PrimeTime / Tempus | 三方案 WNS **+1.13 / +2.29 / +3.06 ns** @50MHz，全 MET |
| **DRC** | KLayout 规则deck | Calibre / ICV | **23 / 23 / 23**（含库级豁免，逐条可追） |
| **LVS** | KLayout LVS | Calibre LVS | 器件级 **240 类型 / 47.4 万实例 100% 匹配** |
| **IREM** | OpenROAD PSM + 静态 EM | RedHawk / Voltus | VDD worst **0.275 mV**、VSS 0.316 mV |
| **LEC** | Yosys `equiv` | Formality / Conformal | 综合前后、APR 前后全通过 |
| **低功耗** | UPF 检查清单 | VC LP | 电源域接口无 ISO/LS 缺失 |

三方案（基线 / +张量核 / +AI 负载约束）的 WNS 逐级改善，证明
**"负载特征能反过来指导物理实现"**：门数 281,881 → 315,271（+11.8%）的同时时序反而更好。

---

## 8. 与晶圆厂签核

> 本仓库在**可流片的开源工艺**上把全流程跑通；正式流片仍需与晶圆厂按其 PDK 与 deck 签核。

### 交付包（本仓库 `flow/` 可产出前六项）

1. 填充后 **GDSII**（mask 数据准备起点）
2. 门级 **Verilog** 网表
3. **CDL / SPICE** 原理图网表（LVS 交叉核对）
4. **SDC** 时序约束
5. **SPEF** 寄生参数
6. STA / DRC / LVS / IREM **签核报告**
7. 引脚 / 凸点坐标（封装对齐）
8. 层映射与 fill 策略说明

### 配合流程

```
我方交付 ──▶ 晶圆厂用【自己的 deck + 自己的 PDK 版本】重跑
              ├─ DRC / LVS / 天线 / 密度
              ├─ 时序复核（foundry 提供的 corner）
              └─ mask data prep（OPC / 数据膨胀）
           ◀── 反馈违规清单 ──▶ 修复 → 重交付（迭代）
           ──▶ 最终 mask tapeout
```

要点：

- **同一份 GDS 在两套 deck 下结果不同是正常的**，按 foundry 的 deck 修，不要用开源通过数去反驳；
- 提前索取 foundry 的 **DRC/LVS deck 与运行脚本模板**，接进 `flow/` 做本地预检；
- 迭代成本主要来自 mask data prep 的重复，**收敛前不要频繁送**；
- 商业 PDK 是**授权物**，需 NDA；本仓库**不分发 PDK**，`.gitignore` 已排除
  `pdk/`、`*.lib`、`*.lef`、`*.nxtgrd`、`*.itf`。

详见 [`skills/foundry-handoff/SKILL.md`](skills/foundry-handoff/SKILL.md)。

---

## 9. 换到 SMIC / TSMC 等商业先进工艺

**流程脚本、约束生成、DFT/ATPG 算法、诊断知识库都不随工艺变化** ——
真正随工艺变的只有四类输入，而它们全部是环境变量：

| PDK 组成 | 开源工艺 | 商业工艺（SMIC / TSMC 等） |
|---------|---------|--------------------------|
| 时序/功耗库 | `<platform>/*.lib` | 各 corner `.lib`（CCS/ECSM，含 SI） |
| 几何库 | `.lef` | 各层 `.lef` + tech file |
| 物理验证规则 | KLayout deck | Calibre / ICV rule deck |
| 层映射 / RC | layers map + 提取规则 | StarRC / QRC 的 `.nxtgrd` / `.itf` |

```bash
export PDK_ROOT=/path/to/foundry/pdk
export SKY130_LIB=$PDK_ROOT/libs/<corner>.lib    # 变量名保留，语义=目标工艺库
bash flow/env.sh --check
```

### 先进节点会新增哪些签核维度

| 维度 | 开源单 corner | 先进节点新增 |
|------|--------------|-------------|
| 时序 | 单库单 corner | 多 corner/mode（MMMC）、OCV/AOCV/POCV、SI 串扰 |
| 物理验证 | 基础 DRC/LVS | 多重曝光、密度、天线、DFM 全套 |
| 电源 | 静态 IR | 动态 IR/EM（VCD 向量）、di/dt |
| 等价性 | 综合/APR 前后 | RTL vs 门级全流程形式验证 |
| DFT | 裸扫描链 + stuck-at | EDT 压缩、OCC、at-speed、MBIST、boundary scan |

**这些新增项正是商业 EDA 的用武之地**，本仓库负责把"方法"验证正确、把流程编排好，
让正式签核阶段的迭代成本降到最低。

---

## 10. 衔接商业 EDA

开源链与商业链读写的是**同一套工业标准交换格式**，所以交接是"换工具"，不是"重写流程"。

| 阶段 | 本仓库（开源） | 商业对应 | 交接格式 |
|------|--------------|---------|---------|
| 综合 | Yosys（`abc -D` 约束驱动） | Design Compiler / Fusion Compiler | 网表 + SDC |
| APR | OpenROAD | ICC2 / Innovus | DEF / Verilog |
| 时序签核 | OpenSTA + OpenRCX | PrimeTime / Tempus | SDC + SPEF |
| 物理验证 | KLayout | Calibre / ICV | GDSII + CDL |
| 电源 | OpenROAD PSM | RedHawk / Voltus | DEF + SPEF + SAIF/VCD |
| 等价性 | Yosys `equiv` | Formality / Conformal | RTL + 网表 |
| DFT | 自研 SCAN/ATPG | Tessent / TetraMAX | 网表 + 测试协议 |

**没有任何私有格式参与交接** —— 这是"开源验证方法 + 商业正式签核"这条路线成立的根本原因。

### 开源做不了、必须交给商业链的清单

多 corner 统一收敛（MMMC）、OCV/AOCV/POCV、SI 签核、动态 IR/EM、
UPF 静态验证（VC LP 级）、EDT/MBIST、先进节点 DRC。
开源工具也缺部分专有命令（`set_instance_region`、`set_shielded_net`），
本仓库用 `group_path`（SDC）+ PDN 加倍做**语义等价替代**，并在报告中如实标注。

详见 [`skills/commercial-eda/SKILL.md`](skills/commercial-eda/SKILL.md)。

---

## 11. 规则引擎怎么用

```bash
# 1) 报告诊断（默认离线规则引擎，可切 LLM）
python3 -m engine analyze --stage TIMING --report reports/sta.rpt --no-llm

# 2) 坑库检索（把报错文本丢进去）
python3 -m engine pitfalls --text "Signal 11 ... makePortFuncs ... IQ"

# 3) 网表 → 负载特征 → 实例级约束 TCL
python3 -m engine bind design.v flow/openroad/inst_bind.tcl

# 4) 闭环迭代：跑流程 → 解析 → 诊断 → 记录修复 → 重跑
python3 -m engine optimize --stage TIMING --run "make sta" --reports wns.rpt \
        --metrics wns,tns --iterations 5 --no-llm
```

**三种模式**（`engine/config.example.json` → 复制为 `engine/config.json`）：

| 模式 | 说明 |
|------|------|
| `offline`（默认） | 纯规则引擎，零网络依赖 |
| `openai` | 任意 OpenAI 兼容端点 |
| `ollama` | 本地 Ollama（如 `qwen2.5-coder:14b`） |

无论哪种模式，**诊断路径都是 LLM 优先、失败自动回退规则引擎**，
且始终附带坑库命中，保证可追溯。

**扩展方式**：新增经验改 `rules/*.yaml`，引擎代码不含任何硬编码规则。

---

## 12. 能力边界（重要）

| 本仓库负责 | 不负责（交给商业链） |
|-----------|-------------------|
| 在可流片工艺上把方法跑通、算法验证正确 | 正式流片签核 |
| 流程编排、约束生成、诊断知识沉淀 | 多 corner/SI/动态 IR 收敛 |
| 把经验变成 agent 可消费的资产 | 替代 EDA 引擎 |

**不要把开源签核结果宣传为 foundry 签核通过。** 两者 deck 与 PDK 版本都不同源。

---

## 13. 依赖与许可

**一键检查 / 安装依赖** —— 知识库与规则引擎只需要 core 档：

```bash
./install-deps.sh --check      # 只检查缺什么，不动系统
./install-deps.sh --install    # 按平台安装（macOS/Homebrew、Debian/Ubuntu、RHEL）
./install-deps.sh --dry-run    # 只打印将执行的命令
./install-deps.sh --with-orfs  # 额外克隆并编译 OpenROAD-flow-scripts（1–3 小时）
```

| 档 | 工具 | 用途 |
|----|------|------|
| **core** | `python3` + `PyYAML`、`iverilog` | 规则引擎、仿真出波形图 —— **只用知识库/引擎的话装这些就够** |
| **signoff** | `yosys`、`klayout`、`openroad` | 综合、DRC/LVS/版图渲染、APR/STA/IREM |
| **extra** | `verilator`、`gtkwave` | 更快的仿真、波形 GUI（可选） |

`klayout` 与 `openroad` 在多数发行版没有官方包，脚本会打印手动安装方式
（Homebrew cask / 官方 .deb / 源码编译 / Docker 镜像 `openroad/orfs`）。
**装不上 EDA 工具也不影响知识库与规则引擎的使用** —— 那部分是这个仓库的本体。

- **许可**：[Apache-2.0](LICENSE)

---

## 14. 贡献

最有价值的贡献是**往坑库里加一条**：

```yaml
- id: PIT-011
  title: <一句话症状>
  stage: <SYN|APR|TIMING|PV|IREM|LEC|VCLP|...>
  symptom: ["<报错关键词1>", "<关键词2>"]
  diagnosis: >
    根因是什么。
  fix: |
    具体怎么改（能给命令/脚本就给）。
  verify: 改完怎么确认好了。
  keywords: [关键字, 供检索]
```

一条坑救全组。新增后跑 `make test` 确认解析通过。
