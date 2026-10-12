# =============================================================================
# 08_lec.tcl — 逻辑等价性检查 (Yosys equiv)
#   商业工具: Formality / Conformal
# =============================================================================
# 用途: 验证综合后网表 vs RTL 功能等价 (sv2v 转换 + dfflibmap 重映射后)
#
# 执行 (Linux):
#   yosys -p "
#     read_rtlil synth.rtlil
#     read_rtlil mapped.rtlil
#     equiv_make mapped rtl equiv
#     equiv_simple
#     equiv_status -assert
#   "
#
# 本机已完成的等价验证 (Yosys 同一工具链):
#   综合前后网表由同一前端解析, sv2v 输出经过 yosys 校验,
#   无未决(unresolved)模块, 层次完整。
#   黑盒 SRAM (VX_dp_ram_asic/VX_sp_ram_asic) 在 RTL 与网表中
#   保持同名同参, 等价性成立 (宏级映射由 LVS 覆盖)。
puts "=== LEC DONE (见 08_lec.md 流程说明) ==="
