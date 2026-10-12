# =============================================================================
# 03_cts.tcl — 时钟树综合 (H-tree + mesh, MAC 阵列 skew 控制)
# =============================================================================
source ./env.tcl

read_lef $TECH_LEF
read_lef $MACRO_LEF
read_def $DEF_IN
read_sdc $SDC

# ---- 时钟树目标 (LLM 负载: 大扇出 GEMM 阵列) ----
set_wire_rc -layer metal2
set_wire_rc -clock -layer metal5

# skew 目标: MAC 阵列扇出大, 采用 H-tree, skew 预算 30ps
create_clock_tree_spec -buffer_list {CLKBUF_X1 CLKBUF_X2 CLKBUF_X3} \
    -max_fanout 32 -sink_clustering_enable
clock_tree_synthesis -buf_list {CLKBUF_X1 CLKBUF_X2 CLKBUF_X3} \
    -root_buf CLKBUF_X3 -sink_clustering_enable \
    -target_skew 30 -target_slew 60

# ---- 时钟树后优化 ----
set_propagated_clock [all_clocks]
repair_clock_nets
repair_timing -setup

# ---- 保持时序 ----
repair_timing -hold

detailed_placement
report_clock_skew
report_checks -path_delay min_max
puts "=== CTS DONE ==="
