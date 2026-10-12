# =============================================================================
# 06_pv.tcl — 物理验证 (DRC/LVS/天线/ERC 签核)
# =============================================================================
source ./env.tcl

read_lef $TECH_LEF
read_lef $MACRO_LEF
read_def $DEF_IN

# ---- DRC (OpenROAD 内置检查; 商业流程: Calibre/ICV) ----
set drc_report "signoff/drc.rpt"
check_metal_density -report_file signoff/metal_density.rpt
catch {detailed_route_check -report $drc_report}
set violations [get_drc_errors]
puts "DRC violations: [llength $violations]"
foreach v $violations {
    puts "  DRC: [$v type] at [$v bbox]"
}

# ---- 天线检查 ----
check_antennas -report_file signoff/antenna.rpt

# ---- LVS (Magic/Klayout 提取; 商业流程: Calibre LVS) ----
# GDS 导出 + 网表比对
write_gds $GDS_OUT
puts "GDS 已导出: $GDS_OUT"
puts "LVS: 在 Linux 用 magic -dnull -noconsole lvs.tcl 执行 (见 lvs.tcl)"
puts "=== PV DONE ==="
