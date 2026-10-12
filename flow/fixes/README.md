# 修复脚本（flow/fixes/）

这里收的都是「流程跑挂了、原因已经查清、改动很小、但下次还会忘」的修复。
**每条修复都对应 `rules/pitfalls.yaml` 里的一个坑**，id 一一对齐，所以 agent 读到坑的词条，
就能直接找到对应的可执行脚本，不用重新推一遍。

## 总入口

```bash
./flow/fixes/apply_fixes.sh --list              # 列出全部修复
./flow/fixes/apply_fixes.sh --show <id>         # 看某条的症状、根因、用法
./flow/fixes/apply_fixes.sh --check             # 环境自检，不改任何文件
./flow/fixes/apply_fixes.sh --check <id> <参数>  # 只诊断某一条
./flow/fixes/apply_fixes.sh --apply <id> <参数>  # 应用某一条
./flow/fixes/apply_fixes.sh --selftest          # 跑各脚本的内置样例
```

约定：**所有脚本都支持「只看不改」**。`--check` 一定是只读的，会改文件的动作只在没有 `--check`
时发生。

## 五条修复

| id | 脚本 | 症状 | 参数 |
|---|---|---|---|
| `spef` | `fix_spef_negidx.py` | STA `read_spef` 报 `[ERROR STA-1670] syntax error` | `<in.spef> [out.spef]` |
| `cdl` | `fix_cdl.py` | LVS 读不进网表 / 器件数对不上，CDL 的 `X` 行末尾缺单元名 | `<cdl> <6_final.v>` |
| `conb` | `fix_conb_cdl.py` | LVS 卡在 conb 单元：原理图有实例、版图提取网表里没有 | `<cdl>` |
| `dfflib` | `gen_dff_libs.py` | 综合报 `$_DFFE_PP_ cannot be legalized` / DFF 映射不上 | `<原始.lib> <输出目录>` |
| `stack` | `run_with_stack.sh` | detail route 崩溃 Signal 11，栈回溯落在 `boost::polygon::MaxCover` | `<命令...>` |

## 各条要点

### `spef` — SPEF 负索引毒 token

OpenRCX 的 SPEF writer 把负索引总线名写成 `mem_req_addr[\-1]`。`[0]` 这类正常索引 OpenSTA
能容忍（87 万行里绝大多数是这种），**致命的是 `[\-1]` 里的反斜杠** —— 词法器在 bus index 里
遇到转义符即报 syntax error。

- 正确修法：`\[-1\]`（括号转义 + 去掉减号前的反斜杠）
- **直觉修法 `\[\-1\]` 依然报错，已实测**
- base 版 789MB SPEF 里 `[\-N]` 只有 63 处，修完 21,877,246 行全量解析通过
- 修完只需重跑 `6_report`，**不必重跑布线与寄生提取**

顺带一个坑中坑：这个脚本的 docstring 必须是 raw string（`r` 前缀）。普通字符串里的 `\[`
会被当成未知转义序列，Python 3.12+ 往 stderr 发 `SyntaxWarning`；而流程脚本用 Tcl `exec`
调它时，**stderr 上的任何输出都会被当成执行失败**。

### `cdl` / `conb` — LVS 前置的两个网表清理

- `cdl`：OpenROAD 的 `write_cdl` 偶尔漏掉 `X` 实例行末尾的单元名。从 APR 的 `6_final.v`
  反查「实例 → 单元类型」补回去。
- `conb`：tie cell 在版图提取网表里被 tie 金属短路掉了（LO→VGND、HI→VPWR），原理图 CDL
  里却还留着 `conb` 实例，LVS 自然对不上。按版图的真实连接改写原理图 CDL，并删掉不再被
  引用的 conb SUBCKT。改名用词边界匹配，避免 `HI_2` 被 `HI` 的替换误伤。

**两个脚本默认就地覆盖目标文件**，动生产产物前先复制一份。

### `dfflib` — 双库策略（源项目里只有引用，没有脚本）

yosys 的 `dfflibmap` 与 abc / OpenSTA 对触发器 Q 引脚 `function` 的要求互相冲突：

- `dfflibmap` 要 Q 的 `function` 是 `IQ` / `IQ_N`，且 ff 组带 clear/preset，才能把
  `$_DFF_PP_` 这类内部触发器映射到具体单元；
- abc / OpenSTA 要 Q 的 `function` 是 `D` / `!D`，遇到 `IQ` 直接解析失败。

一份库满足不了两边，所以在综合流程里同时喂两份（见 `flow/02_synth_sky130.sh` 的
`LIB_DFFMAP` / `LIB`）：

```bash
python3 flow/fixes/gen_dff_libs.py --inspect sky130_fd_sc_hd__tt_025C_1v80.lib
python3 flow/fixes/gen_dff_libs.py --apply   sky130_fd_sc_hd__tt_025C_1v80.lib build/apr
python3 flow/fixes/gen_dff_libs.py --check   build/apr
```

输出名与流程脚本的约定一致：`<stem>_dffmap.lib` / `<stem>_patched.lib`。

**先跑 `--inspect`**。它会报出库里有多少单元、Q 引脚 `function` 的实际取值分布、ff 组里
有没有 clear/preset。如果输出和脚本顶部的假定对不上，说明这版库结构不同，改规则再跑，
别硬 apply。`--apply` 遇到 0 处改动会返回非 0 并告警，不会静默产出一份没变的库。

### `stack` — 抬高栈上限

detail route 的 Signal 11 是布线器递归深度超过默认栈上限，不是设计或 PDK 的问题，
**重跑多少次都一样**。必须把 `ulimit` 抬在「跑布线器」这一层，在外层设置没有用。

```bash
./flow/fixes/run_with_stack.sh openroad -exit flow/openroad/04_route.tcl
source ./flow/fixes/run_with_stack.sh --export     # 给当前 shell 生效
STACK_KB=131072 ./flow/fixes/run_with_stack.sh <命令...>
```

## 这些修复为什么脚本化

坑库（`rules/pitfalls.yaml`）解决「知道该怎么做」，脚本解决「不用每次手敲」。两者叠起来，
agent 才可能真正做到：读到报告里的报错 → 匹配到坑 → 直接调脚本改掉 → 重跑验证，
而不是每一步都回头问人。

## 加一条新修复

1. 脚本放本目录，**必须**支持只读诊断（能用 `--check` 就绝不写文件）
2. 在 `apply_fixes.sh` 的 `FIX_IDS` 加 id，并补 `fix_script` / `fix_title` / `fix_symptom` /
   `fix_usage` / `fix_needs_file` 五个 `case` 分支
3. 在 `rules/pitfalls.yaml` 加同 id 的词条，让坑和脚本互指
