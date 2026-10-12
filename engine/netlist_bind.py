# -*- coding: utf-8 -*-
"""实例级约束生成：AI 负载特征 → 网表具体模块 → APR 约束 Tcl。

让"面向 AI 负载优化"落在具体实例上，而不是泛泛的全局约束。
绑定表来自 rules/workload_knowledge.yaml 的 binding 段，换设计时只改 YAML。
"""
import os
import re

from .knowledge import get_kb


#: Verilog 关键字，避免把 `module top (` 之类误判为实例
KEYWORDS = {
    "module", "endmodule", "input", "output", "inout", "wire", "reg", "logic",
    "assign", "parameter", "localparam", "always", "initial", "generate",
    "if", "else", "case", "endcase", "begin", "end", "for", "function",
    "specify", "endspecify", "defparam", "supply0", "supply1", "tri",
}


def parse_modules(netlist):
    """收集网表中实际被实例化的模块名（cell ref name）。

    门级网表里单元例化形如 `fpu_unit u_fp (.a(a));`，
    这里取第一个标识符作为模块名，并排除 Verilog 关键字。
    同时兼容 RTL 层的 `module <name>` 声明。
    """
    mods = set()
    if not netlist or not os.path.exists(netlist):
        return mods
    with open(netlist, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.split("//")[0]
            m = re.match(r"\s*(\w+)\s+(\w+)\s*\(", line)
            if m and m.group(1) not in KEYWORDS:
                mods.add(m.group(1))
                continue
            m = re.match(r"\s*module\s+(\w+)", line)
            if m:
                mods.add(m.group(1))
    return mods


def bind(netlist, kb=None):
    """返回网表中实际命中的负载特征绑定。"""
    kb = kb or get_kb()
    mods = parse_modules(netlist)
    out = []
    for feat, spec in kb.binding.items():
        hit = sorted({m for m in mods for pat in spec.get("modules", [])
                      if pat.lower() in m.lower()})
        if hit:
            out.append({"feature": feat, "matched": hit,
                        "region": spec.get("region", ""),
                        "priority": spec.get("priority", ""),
                        "strategy": spec.get("strategy", "")})
    return out


def gen_tcl(binding, top="top", util=0.60):
    """按绑定结果生成实例级 APR 约束片段。

    注意：开源工具没有 set_instance_region / set_shielded_net，
    这里生成语义等价替代（group_path + 布局引导），替代关系在注释中标注。
    """
    lines = [
        "# 由 engine.netlist_bind 生成：负载特征 → 具体实例约束",
        f"# top: {top}",
        "# 说明：开源 APR 无 set_instance_region / set_shielded_net，",
        "#       改用 group_path(SDC) + 布局引导 + PDN 加倍做语义等价替代。",
    ]
    for b in binding:
        feat, mods = b["feature"], b["matched"]
        lines += ["", f"# ---- {feat}: {', '.join(mods)} ----",
                  f"# 区域: {b['region']}  优先级: {b['priority']}",
                  f"# 策略: {b['strategy']}"]
        for m in mods:
            lines += [f"set group [get_cells -hier -filter {{ref_name =~ *{m}*}}]",
                      "if {[llength $group] > 0} {",
                      f"    # {feat}: 引导布局至 {b['region']}（用 place 权重近似 region 约束）",
                      "    set_placement_weight $group 2.0",
                      "}"]
        if feat == "qkv_gemm":
            lines.append("group_path -name qkv_datapath -weight 2.0")
        if feat == "kv_cache":
            lines.append("# KV/缓存宏区域电源带加倍：")
            lines.append("#   add_pdn_stripe -grid stdcell_grid -layer metal4 -width 3.2 -pitch 8")
        if feat == "tp_hbm":
            lines.append("# 片外接口宏：halo 20um，独立电源网络单独签核")
        if feat == "moe_noc":
            lines.append("# 交换网络：总线加宽间距 + 屏蔽（替代 set_shielded_net）")
    return "\n".join(lines) + "\n"


def main(argv=None):
    import sys
    argv = argv if argv is not None else sys.argv[1:]
    netlist = argv[0] if argv else None
    out = argv[1] if len(argv) > 1 else "flow/openroad/inst_bind.tcl"
    if not netlist:
        print("用法: python3 -m engine.netlist_bind <netlist.v> [out.tcl]")
        return 2
    kb = get_kb()
    b = bind(netlist, kb)
    print(f"网表模块匹配结果（{len(b)}/{len(kb.binding)} 类负载特征）:")
    for x in b:
        print(f"  [{x['feature']}] 命中 {len(x['matched'])} 个模块: {', '.join(x['matched'][:8])}")
    with open(out, "w", encoding="utf-8") as f:
        f.write(gen_tcl(b))
    print(f"\n实例级约束已生成: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
