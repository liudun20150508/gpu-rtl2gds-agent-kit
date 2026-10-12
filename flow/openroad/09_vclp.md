# 09_vclp.md — 低功耗验证 (VCLP: VC LP 等价开源替代)

VCLP = VC Low Power (Synopsys), 验证 UPF 电源意图在网表中的实现合法性。

## 本设计的电源意图 (UPF 摘要)

```upf
create_power_domain PD_CORE -include_scope
create_power_domain PD_EXPERT0 -elements {expert0}   # MoE 专家 0, 可下电
create_power_domain PD_EXPERT1 -elements {expert1}   # MoE 专家 1, 可下电
create_supply_port VDD_GATED
create_supply_net VDD_GATED -domain PD_EXPERT0
create_supply_net VDD_GATED -domain PD_EXPERT1
# 隔离单元: 下电域输出 -> 常开域
set_isolation iso_expert -domain PD_EXPERT0 -isolation_power_net VDD -clamp_value 0
# 电平转换: 跨域信号 (LS 单元由综合/PR 自动插入)
set_level_shifter ls_vddg -domain PD_EXPERT0
```

## 验证清单 (VCLP 对应项)

| # | 检查项 | 方法 | 结果 |
|---|--------|------|------|
| 1 | 隔离单元插入: 所有下电域输出均已加 ISO 单元 | 网表搜索 ISO* 实例 | 待跑 |
| 2 | 电平转换器: 跨电压域网络无缺失 LS | 网表搜索 LVL* 实例 | 待跑 |
| 3 | 常开网络: 下电域内 always-on 路径合法 (复位/时钟) | UPF 仿真 | 待跑 |
| 4 | 电源开关链: switch 单元级联深度 < 限制 | 网表分析 | 待跑 |
| 5 | retention 触发器: 状态保持单元配对正确 | LEC + UPF | 待跑 |

## 执行 (Linux)

```bash
# Synopsys:  vclp -f vclp.tcl
# 开源替代: UPF 感知仿真 (iverilog + upf 插件) 或手工网表检查清单
```

## 与 LLM 负载的关联
MoE 稀疏激活 -> 专家阵列分电源域下电, 空闲专家功耗趋近 0,
这是大模型推理芯片相比传统 GPU 的显著低功耗优势。
