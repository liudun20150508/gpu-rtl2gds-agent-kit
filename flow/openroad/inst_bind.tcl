# 由 llm_eda.netlist_bind 生成: 负载特征 -> 具体实例约束
# top: Vortex

# ---- kv_cache: VX_cache_data, VX_cache_mshr, VX_cache_tags ----
# 策略: 宏双 bank 错开读写端口; 电源带加倍; 时钟 gating 分组
set group [get_cells -hier -filter 'ref_name =~ *VX_cache_data*']
if {[llength $group] > 0} {
    set_instance_region $group kv_cache_region -util 0.6
}
set group [get_cells -hier -filter 'ref_name =~ *VX_cache_mshr*']
if {[llength $group] > 0} {
    set_instance_region $group kv_cache_region -util 0.6
}
set group [get_cells -hier -filter 'ref_name =~ *VX_cache_tags*']
if {[llength $group] > 0} {
    set_instance_region $group kv_cache_region -util 0.6
}
# KV 宏区域电源带加倍: add_pdn_stripe -grid stdcell_grid -layer metal5 -width 3.2 -pitch 8 -region kv_cache_region

# ---- qkv_gemm: VX_fma_unit, VX_fpu_std, VX_wallace_mul ----
# 策略: 数据通路直通布局; retiming 平衡流水级; skew<30ps
set group [get_cells -hier -filter 'ref_name =~ *VX_fma_unit*']
if {[llength $group] > 0} {
    set_instance_region $group qkv_gemm_region -util 0.6
}
set group [get_cells -hier -filter 'ref_name =~ *VX_fpu_std*']
if {[llength $group] > 0} {
    set_instance_region $group qkv_gemm_region -util 0.6
}
set group [get_cells -hier -filter 'ref_name =~ *VX_wallace_mul*']
if {[llength $group] > 0} {
    set_instance_region $group qkv_gemm_region -util 0.6
}
group_path -name qkv_datapath -weight 2.0

# ---- moe_noc: VX_matrix_arbiter, VX_priority_arbiter, VX_rr_arbiter, VX_stream_switch, VX_stream_xbar ----
# 策略: 等距布局, 路由链均衡; 总线加 shield; 专家区域可下电
set group [get_cells -hier -filter 'ref_name =~ *VX_matrix_arbiter*']
if {[llength $group] > 0} {
    set_instance_region $group moe_noc_region -util 0.6
}
set group [get_cells -hier -filter 'ref_name =~ *VX_priority_arbiter*']
if {[llength $group] > 0} {
    set_instance_region $group moe_noc_region -util 0.6
}
set group [get_cells -hier -filter 'ref_name =~ *VX_rr_arbiter*']
if {[llength $group] > 0} {
    set_instance_region $group moe_noc_region -util 0.6
}
set group [get_cells -hier -filter 'ref_name =~ *VX_stream_switch*']
if {[llength $group] > 0} {
    set_instance_region $group moe_noc_region -util 0.6
}
set group [get_cells -hier -filter 'ref_name =~ *VX_stream_xbar*']
if {[llength $group] > 0} {
    set_instance_region $group moe_noc_region -util 0.6
}
set_shielded_net [get_nets -hier -filter "name =~ *xbar*"]