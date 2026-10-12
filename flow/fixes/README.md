# SPEF STA-1670 修复 (fix_spef_negidx.py)

## 现象
6_report 阶段 `read_spef` 报 `[ERROR STA-1670] ... syntax error`。
例: base Vortex SKY130 版在 line 502796 报错 (TCU 版在 line 503671, 同构)。

## 根因 (已用 OpenROAD 2.0 bazel 版实测确认)
OpenRCX SPEF writer 把负索引总线名写成 `mem_req_addr[\-1]`:
- `[0]` 这类正常索引 **OpenSTA 可容忍**, 不是 87 万行都需要转义;
- 真正致命的是 `[\-1]` 里的 `\` —— tokenizer 在 bus index 里遇到转义符即 syntax error;
- 修复形态: `\[-1\]` (括号转义 + 去掉减号前的多余反斜杠)。`\[\-1\]` (用户直觉修法) **依然报错**, 已实测。

## 修复范围 (base 版实测)
整个 789MB SPEF 中 `[\-N]` 仅 63 处 (name map 63 行, PORTS/D_NET 引用随 name map 一并替换)。
修复后 21,877,246 行全量解析通过 (exit 0)。

## 用法
python3 flow/fixes/fix_spef_negidx.py <坏.spef> <好.spef>
# 然后只重跑 6_report (read_spef 好.spef + report_timing), 无需重跑布线/提取
