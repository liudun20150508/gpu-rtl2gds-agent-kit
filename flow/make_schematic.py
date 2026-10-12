#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从真实综合网表生成门级原理图 (SKY130 netlist)

用法: python3 flow/make_schematic.py <netlist> <module_name_substr> <out.png>
输出: 拓扑分层排布的门级原理图 PNG + SVG
"""
import re, sys, os, collections

def parse_module(text, name_substr):
    """提取指定模块的实例与连线"""
    parts = re.split(r"^\s*module\s+", text, flags=re.M)[1:]
    target = None
    for p in parts:
        nm = p.split()[0].split("(")[0]
        if name_substr.lower() in nm.lower():
            target = nm; break
    if not target:
        sys.exit(f"模块未找到: {name_substr}")
    body = p
    insts = []
    for m in re.finditer(r"^\s*(sky130_fd_sc_hd__\w+)\s+(\S+)\s*\((.*?)\)\s*;", body, re.S | re.M):
        cell, name, pins = m.group(1), m.group(2), m.group(3)
        conns = []
        for pm in re.finditer(r"\.(\w+)\(([^)]*)\)", pins):
            conns.append((pm.group(1), pm.group(2).strip()))
        insts.append((cell, name, conns))
    # 模块端口
    ports = re.findall(r"^\s*(input|output)\s+(?:\[\d+:\d+\]\s+)?(\w+)", body, re.M)
    return target, insts, ports

def gate_kind(cell):
    c = cell.replace("sky130_fd_sc_hd__", "")
    if c.startswith("df"): return "DFF"
    if c.startswith("mux"): return "MUX"
    if c.startswith("nand"): return "NAND"
    if c.startswith("nor"): return "NOR"
    if c.startswith("inv"): return "INV"
    if c.startswith("and"): return "AND"
    if c.startswith("or"): return "OR"
    if c.startswith("xor"): return "XOR"
    if c.startswith("xnor"): return "XNOR"
    if c.startswith("buf"): return "BUF"
    if c.startswith("oai"): return "OAI"
    if c.startswith("aoi"): return "AOI"
    if c.startswith("a2"): return "AND"
    if c.startswith("o2"): return "OR"
    if c.startswith("fa"): return "FA"
    if c.startswith("ha"): return "HA"
    if c.startswith("clk"): return "BUF"
    if c.startswith("dly"): return "BUF"
    if c.startswith("ebuf"): return "BUF"
    if c.startswith("conb"): return "CONST"
    return "GATE"

def draw_gate(kind, x, y, w=64, h=40, label=""):
    """返回 SVG 图形元素列表"""
    g = []
    if kind == "INV":
        g.append(f'<polygon points="{x},{y} {x+w},{y+h/2} {x},{y+h}" fill="none" stroke="#111" stroke-width="2"/>')
        g.append(f'<circle cx="{x+w+5}" cy="{y+h/2}" r="4" fill="none" stroke="#111" stroke-width="2"/>')
    elif kind in ("NAND","NOR","AND","OR"):
        body = f'<path d="M {x},{y} h {w*0.65} a {h/2},{h/2} 0 0 1 0,{h} h {-w*0.65} z" fill="none" stroke="#111" stroke-width="2"/>'
        g.append(body)
        if kind in ("NAND","NOR"):
            g.append(f'<circle cx="{x+w+5}" cy="{y+h/2}" r="4" fill="none" stroke="#111" stroke-width="2"/>')
        if kind in ("NOR","OR"):
            g.append(f'<path d="M {x+w*0.15},{y} q {w*0.25},{h/2} {w*0.15},{h}" fill="none" stroke="#111" stroke-width="2"/>')
    elif kind in ("XOR","XNOR"):
        g.append(f'<path d="M {x},{y} h {w*0.6} a {h/2},{h/2} 0 0 1 0,{h} h {-w*0.6} z" fill="none" stroke="#111" stroke-width="2"/>')
        g.append(f'<path d="M {x-w*0.18},{y} h {w*0.6} a {h/2},{h/2} 0 0 1 0,{h} h {-w*0.6}" fill="none" stroke="#111" stroke-width="2"/>')
        if kind == "XNOR":
            g.append(f'<circle cx="{x+w+5}" cy="{y+h/2}" r="4" fill="none" stroke="#111" stroke-width="2"/>')
    elif kind == "MUX":
        g.append(f'<polygon points="{x},{y} {x+w},{y+h*0.25} {x+w},{y+h*0.75} {x},{y+h}" fill="none" stroke="#111" stroke-width="2"/>')
    elif kind == "DFF":
        g.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="#111" stroke-width="2"/>')
        g.append(f'<text x="{x+w/2}" y="{y+h*0.6}" font-size="9" text-anchor="middle" font-family="Menlo">{label[:6]}</text>')
    else:
        g.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="#111" stroke-width="2"/>')
    return g

def main():
    net, sub, out = sys.argv[1], sys.argv[2], sys.argv[3]
    text = open(net, encoding="utf-8", errors="ignore").read()
    modname, insts, ports = parse_module(text, sub)
    print(f"模块 {modname}: {len(insts)} 门, {len(ports)} 端口")

    # 拓扑分层 (输入端口层 0)
    net_map = collections.defaultdict(list)   # net -> [(inst, pin)]
    inst_nets = collections.defaultdict(list)
    for cell, name, conns in insts:
        for pin, nets in conns:
            for nn in nets.split(","):
                nn = nn.strip()
                if not nn or nn in ("1'b0", "1'b1", "1'bx", "VDD", "VSS", "VPWR", "VGND", "vdd", "vss"): continue
                net_map[nn].append((name, pin))
                inst_nets[name].append((pin, nn))
    in_nets = {p for _, p in ports if p}
    depth = {}
    def get_depth(name):
        if name in depth: return depth[name]
        depth[name] = 0  # 防环
        d = 0
        for pin, nn in inst_nets[name]:
            if pin in ("Y","Q","X"): continue
            if nn in in_nets: continue
            srcs = [i for i,p in net_map[nn] if p in ("Y","Q","X")]
            for s in srcs:
                d = max(d, get_depth(s) + 1)
        depth[name] = d
        return d
    for cell, name, _ in insts:
        get_depth(name)
    cols = collections.defaultdict(list)
    for cell, name, _ in insts:
        cols[depth[name]].append((cell, name))
    maxd = max(cols) if cols else 0

    CW, RH, X0, Y0 = 150, 70, 60, 40
    pos = {}
    W = X0 + (maxd+1)*CW + 200
    H = max(300, max(len(v) for v in cols.values())*RH + 200)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">',
           f'<rect width="{W}" height="{H}" fill="white"/>',
           f'<text x="20" y="24" font-size="14" font-family="Menlo" font-weight="bold">门级原理图: {modname} ({len(insts)} gates, 真实综合网表)</text>']
    # 输入端口在左侧
    port_y = {}
    pi = 0
    for d, p in ports:
        if p in ("clk","reset"): continue
        port_y[p] = Y0 + 30 + pi*30; pi += 1
        svg.append(f'<text x="10" y="{port_y[p]}" font-size="10" font-family="Menlo" fill="#0369a1">{p}</text>')
    # 门
    for d in range(maxd+1):
        col = cols[d]
        x = X0 + d*CW
        for i, (cell, name) in enumerate(col):
            y = Y0 + i*RH
            pos[name] = (x, y)
            kind = gate_kind(cell)
            svg += draw_gate(kind, x, y)
            svg.append(f'<text x="{x+30}" y="{y+50}" font-size="8" font-family="Menlo" fill="#555">{name[:12]}</text>')
    # 连线
    for cell, name, conns in insts:
        x, y = pos[name]
        for pin, nets in conns:
            if pin in ("A","B","C","D","S","CLK","D","DI","DE"): px, py = x, y+10
            elif pin in ("Y","Q","X"): px, py = x+70, y+20
            else: px, py = x+30, y+20
            for nn in nets.split(","):
                nn = nn.strip()
                if not nn or nn in ("1'b0","1'b1","1'bx","VDD","VSS","VPWR","VGND"): continue
                if nn in port_y:
                    tx, ty = 15, port_y[nn]
                    svg.append(f'<polyline points="{px},{py} {tx},{ty}" fill="none" stroke="#9ca3af" stroke-width="0.8"/>')
                else:
                    for sname, spin in net_map.get(nn, []):
                        if spin not in ("Y","Q","X"): continue
                        if sname == name: continue
                        sx, sy = pos.get(sname, (0,0))
                        svg.append(f'<polyline points="{px},{py} {sx+70},{sy+20}" fill="none" stroke="#9ca3af" stroke-width="0.8"/>')
    svg.append('</svg>')
    svg_path = out.replace(".png", ".svg")
    open(svg_path, "w").write("\n".join(svg))
    print(f"SVG: {svg_path}")
    os.system(f'qlmanage -t -s 1600 -o . "{svg_path}" >/dev/null 2>&1')
    png = svg_path + ".png"
    if os.path.exists(png):
        os.rename(png, out)
        print(f"PNG: {out}")
    else:
        print("PNG 渲染失败 (qlmanage), 保留 SVG")

if __name__ == "__main__":
    main()
