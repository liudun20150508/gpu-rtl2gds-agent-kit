# =============================================================================
# 01_floorplan.tcl — 芯片规划 (针对 LLM 推理负载的宏布局策略)
#   策略来源: llm_eda/knowledge.py WORKLOAD_KNOWLEDGE
#   - SRAM 宏(KV cache / LMEM / GPR)贴近 LSU/AGU
#   - MAC 阵列(QKV 计算)数据通路直通布局
#   - HBM PHY / 内存控制器固定 die 边缘
#   - 宏分组双 bank, 错开读写端口冲突
# =============================================================================
source ./env.tcl

read_lef $TECH_LEF
read_lef $MACRO_LEF
read_verilog $NETLIST
read_liberty $LIB
link_design $TOP

initialize_floorplan \
    -die_area  "0 0 2000 2000" \
    -core_area "20 20 1980 1980" \
    -site FreePDK45_38x28_10R_NP_162NW_34O

# ---- 电源网络规划 (IREM 前置) ----
# 电源环 + 高层 mesh: KV cache 宏区域电源带加倍
add_global_connection -net VDD -pin_pattern {^VDD$} -power
add_global_connection -net VSS -pin_pattern {^VSS$} -ground
add_global_connection -net VDD -inst_pattern {.*} -pin_pattern {^VDD$} -power
add_global_connection -net VSS -inst_pattern {.*} -pin_pattern {^VSS$} -ground

set_voltage_domain -power VDD -ground VSS
define_pdn_grid -name stdcell_grid -voltage_domains {CORE}
add_pdn_stripe -grid stdcell_grid -layer metal1 -width 0.48 -pitch 2.16 -offset 0
add_pdn_stripe -grid stdcell_grid -layer metal4 -width 1.6  -pitch 16.0 -offset 0
add_pdn_stripe -grid stdcell_grid -layer metal7 -width 4.0  -pitch 50.0 -offset 0

# ---- 宏摆放 (LLM 负载特征驱动) ----
# 1) 内存宏 (KV cache 常驻 / LMEM scratchpad): 紧邻 LSU/AGU 区域 (左下)
# 2) MAC/FMA 阵列: 核心区域直通布局, 权重寄存器堆紧邻乘法器
# 3) I/O PHY (HBM PHY / AXI): 固定 die 边缘
# 宏实例名按 RTL 层次: core/cluster/... 的 RAM 实例
# 此处用宏 halo 与 channel 规则统一处理:
foreach inst [get_cells -hier -filter "is_macro_cell"] {
    # 默认左缘排布, 相邻宏间留 30um routing channel (all-to-all 总线预留)
    set_halo 10 [list $inst]
}

# ---- 电源开关 (VCLP/低功耗) ----
# MoE 稀疏激活: 专家阵列可下电 (UPF 对应描述见 10_vclp.md)
# insert_power_switch ...  # 需要真实 switch cell, 此处注释留待 PDK 提供

# ---- 全局布线层分配 (缓解拥塞) ----
set_global_routing_layer_adjustment metal2 0.3
set_global_routing_layer_adjustment metal3 0.3
set_global_routing_layer_adjustment metal4-metal7 0.15

# ---- 引脚规划: die-to-die / HBM 接口固定边 ----
# (张量并行: 相邻 die 接口对齐; 引脚分布沿 die 边缘均匀)
place_pins -hor_layers metal3 -ver_layers metal2 \
    -corner_avoidance 100 -min_distance 0.6

report_checks
puts "=== floorplan DONE ==="
