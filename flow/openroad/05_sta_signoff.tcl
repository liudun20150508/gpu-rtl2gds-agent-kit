# =============================================================================
# 05_sta_signoff.tcl — 时序签核 (OpenSTA, 多 corner)
# =============================================================================
source ./env.tcl

# 多 corner: 快/慢库(此处 PDK 提供 typical 单库, 商业流程替换为
#   slow.lib (setup, 0.9V 125C) + fast.lib (hold, 1.1V -40C))
read_liberty $LIB
read_verilog $NETLIST
link_design $TOP

read_sdc $SDC
read_spef $SPEF

set_propagated_clock [all_clocks]

puts "==== SETUP (max) ===="
report_checks -path_delay max -fields {slew cap input nets} -format full_clock_expanded
report_worst_slack -max
report_wns
report_tns

puts "==== HOLD (min) ===="
report_checks -path_delay min
report_worst_slack -min
report_wns
report_tns

puts "==== CLOCK ===="
report_clock_skew
report_clock_latency
report_clock_min_period

puts "==== DESIGN ===="
report_design_area
report_power
puts "=== STA signoff DONE ==="
