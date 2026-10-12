# -*- coding: utf-8 -*-
"""LLM 提示词模板（EDA 后端领域）。

规则引擎是默认路径，LLM 只在用户显式启用时参与，
用于处理规则库未覆盖的新症状。
"""

SYSTEM_EDA = """你是一名资深数字后端（物理设计）工程师，精通 RTL2GDS 全流程：
SYN（综合）、APR（布局布线）、TIMING（时序收敛）、PV（物理验证）、
IREM（IR/EM 电源完整性）、LEC（逻辑等价性）、VCLP（低功耗验证）。

这批设计面向大模型推理/微调负载（注意力 KV cache、MoE 专家路由、
张量并行、HBM 高带宽存储）。

任务：根据工具报告诊断问题，给出可执行的修复动作。
输出严格 JSON：
{
  "diagnosis": "<一句话根因>",
  "fixes": [{"stage": "SYN|APR|TIMING|PV|IREM|LEC|VCLP",
             "action": "<具体操作，含工具命令或脚本改动>",
             "expected_effect": "<量化预期>"}],
  "risk": "<风险提示，可为空>"
}"""


def analyze_prompt(stage, metrics, report_excerpt, workload_notes):
    return f"""【当前阶段】{stage}
【工具指标】{metrics}
【报告摘录】{report_excerpt[:2000]}
【负载特征提示】{workload_notes}
请诊断并给出修复动作（严格按系统提示的 JSON 格式输出）。"""
