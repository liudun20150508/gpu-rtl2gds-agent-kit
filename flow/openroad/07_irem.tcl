# =============================================================================
# 07_irem.tcl — IR/EM 电源完整性 (OpenROAD PSM)
#   商业工具: RedHawk / Voltus
# =============================================================================
source ./env.tcl

read_lef $TECH_LEF
read_lef $MACRO_LEF
read_def $DEF_IN
read_liberty $LIB
read_sdc $SDC

# ---- 电源网络分析 (静态 IR drop) ----
set_power_net VDD -voltage 1.1
set_ground_net VSS
read_spef $SPEF
read_activity_file -format SAIF $SAIF

# 静态压降分析: 目标 < 5% VDD
analyze_power_grid -net VDD
report_ir_drop -net VDD -report_file signoff/ir_drop.rpt

# ---- EM 检查 ----
# 高电流路径: KV cache 写端口 / HBM PHY 供电 / MAC 阵列
analyze_em -net VDD -report_file signoff/em.rpt

puts "=== IREM DONE ==="
puts "备注: 动态压降 (di/dt) 分析需要 VCD/FSDB, 商业工具 RedHawk/Voltus 支持"
