# =============================================================================
# 04_route.tcl — 布线 (全局+详细, 天线修复, PT-SI 防护)
# =============================================================================
source ./env.tcl

read_lef $TECH_LEF
read_lef $MACRO_LEF
read_def $DEF_IN
read_sdc $SDC

set_wire_rc -layer metal2
set_wire_rc -clock -layer metal5
set_propagated_clock [all_clocks]

# ---- 全局布线 ----
global_route -guide_file guides.route

# ---- 详细布线 (可多次迭代收敛 DRC) ----
for {set i 0} {$i < 5} {incr i} {
    detailed_route -drc_report drc_$i.rpt
    set n [llength [get_drc_errors]]
    puts "drc iter $i: $n violations"
    if {$n == 0} break
    detailed_route -repair
}

# ---- 天线修复 ----
repair_antennas

# ---- 串扰防护 (all-to-all 总线长线) ----
# 对 NoC/all-to-all 交换总线添加屏蔽线, 降低 PT-SI 失效
foreach net [get_nets -hier -filter "name =~ *mem*req* || name =~ *xbar*"] {
    set_shielded_net $net
}

# ---- 时序修复 ----
estimate_parasitics -global_routing
repair_timing -setup -hold

# ---- 填充与金属填充 ----
filler_placement FILLCELL_X1 FILLCELL_X2 FILLCELL_X4 FILLCELL_X8
set_metal_fill -layer metal1 -density 0.3 -region [ord::get_core_bbox]
global_metal_fill

write_def $DEF_OUT
report_worst_slack
report_congestion
report_design_area
puts "=== route DONE ==="
