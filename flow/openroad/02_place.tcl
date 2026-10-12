# =============================================================================
# 02_place.tcl — 布局 (全局+详细布局, LLM 负载特征分组)
# =============================================================================
source ./env.tcl

read_lef $TECH_LEF
read_lef $MACRO_LEF
if {[file exists $DEF_IN]} {
    read_def $DEF_IN
} else {
    source ./01_floorplan.tcl
}

# ---- 关键路径分组 (QKV 数据通路优先级) ----
# 对 attention score 计算路径设置高优先级, 使 GEMM 数据通路布线短直
group_path -name qkv_datapath -weight 2.0

# ---- 全局布局 ----
global_placement -density 0.62 -pad_left 2 -pad_right 2

# ---- 拥塞修复循环 (all-to-all 总线区域) ----
for {set i 0} {$i < 3} {incr i} {
    estimate_parasitics -placement
    set cong [sta::worst_slack]
    puts "iter $i slack=$cong"
    if {$cong >= 0} break
    repair_design -max_wire_length 600
}

# ---- 详细布局 ----
detailed_placement

# ---- 时序预估 ----
estimate_parasitics -placement
report_worst_slack
report_congestion -overflow

# ---- 填充 tap/endcap ----
tapcell -distance 14 -tapcell_master TAPCELL_X1 -endcap_master TAPCELL_X1
filler_placement FILLCELL_X1 FILLCELL_X2 FILLCELL_X4 FILLCELL_X8

report_checks
puts "=== place DONE ==="
