#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基于真实综合面积的 Floorplan 版图草案生成器

输入: build/vortex_base/reports/stat_full.rpt (yosys 实测模块面积)
策略: llm_eda.netlist_bind 的负载特征 -> 区域布局
  - kv_cache (SRAM 宏+缓存): 左下, 贴近 LSU/AGU
  - qkv_gemm (FMA/ALU/FPU): 中心数据通路直通
  - moe_noc (仲裁/交换): 中心环
  - tp_hbm (AXI/IO): die 边缘
输出: out/floorplan.gds + out/floorplan.png + 文本版图
"""
import re, os, sys
sys.path.insert(0, ".")
import gdspy
from llm_eda.netlist_bind import BINDING

BUILD = "build/vortex_base"
RPT = f"{BUILD}/reports/stat_full.rpt"

# ---- 1. 解析真实模块面积 ----
text = open(RPT, encoding="utf-8", errors="ignore").read()
mod_areas = {}
for m in re.finditer(r"Chip area for module '(\\?\$?paramod\\?[^']*?\\?)?\\?(\w+)':\s*([\d.]+)", text):
    pass
# 更稳的解析: 抓所有 "Chip area for module '<name>': <area>"
for m in re.finditer(r"Chip area for module '([^']+)':\s*([\d.]+)", text):
    name, area = m.group(1), float(m.group(2))
    if area <= 0:
        continue
    # 取干净模块名 (去 paramod 前缀)
    base = name.split("\\")[-1].replace("$paramod", "")
    base = re.sub(r"=.*", "", base)
    if base not in mod_areas or area > mod_areas[base]:
        mod_areas[base] = area

top_area_m = re.search(r"Chip area for top module '[^']*':\s*([\d.]+)", text)
total_std = float(top_area_m.group(1)) if top_area_m else sum(mod_areas.values())
sram = 57079.2  # sram_cost.py 实测

print(f"解析到 {len(mod_areas)} 个模块, 标准单元总面积 {total_std:.0f} um^2")

# ---- 2. 负载特征分组 ----
groups = {k: {"area": 0.0, "mods": []} for k in BINDING}
groups["other"] = {"area": 0.0, "mods": []}
for name, area in sorted(mod_areas.items(), key=lambda x: -x[1]):
    for feat, spec in BINDING.items():
        if name in spec["modules"]:
            groups[feat]["area"] += area
            groups[feat]["mods"].append((name, area))
            break
    else:
        groups["other"]["area"] += area
        groups["other"]["mods"].append((name, area))

# ---- 3. 面积 -> die 尺寸 ----
total_area = total_std + sram
util = 0.70
die_size = (total_area / util) ** 0.5
die = die_size / 1000.0  # um -> mm
print(f"die 尺寸: {die:.3f} mm x {die:.3f} mm (util={util})")

# ---- 4. 布局策略 (坐标单位 mm) ----
W = die
regions = {
    "kv_cache": (0.02*W, 0.02*W, 0.38*W, 0.45*W),   # 左下: KV/LMEM/GPR 宏
    "qkv_gemm":  (0.30*W, 0.30*W, 0.70*W, 0.70*W), # 中心: FMA/ALU 数据通路
    "moe_noc":   (0.38*W, 0.38*W, 0.62*W, 0.62*W), # 中心环: 交换/仲裁
    "tp_hbm":    (0.0, 0.0, W, 0.10*W),            # 上边缘: AXI/HBM PHY
    "other":     (0.10*W, 0.10*W, 0.90*W, 0.90*W), # 其余: 环绕散布
}
COLORS = {"kv_cache": "#3B82F6", "qkv_gemm": "#EF4444", "moe_noc": "#10B981",
          "tp_hbm": "#F59E0B", "other": "#9CA3AF", "sram": "#1D4ED8"}

# ---- 5. 生成 GDS ----
lib = gdspy.GdsLibrary(name="VortexFloorplan", unit=1e-6, precision=1e-9)
cell = lib.new_cell("Vortex_FLOORPLAN")

def rect(x0, y0, x1, y1, layer, datatype=0):
    cell.add(gdspy.Rectangle((x0*1000, y0*1000), (x1*1000, y1*1000), layer=layer, datatype=datatype))

# die 边界
rect(0, 0, W, W, layer=100)

# SRAM 块 (KV cache 宏区): 面积 57079 um^2 分成 16 个宏
import math
sram_blocks = 16
sb = (sram / sram_blocks) ** 0.5 / 1000.0  # mm
kx0, ky0, kx1, ky1 = regions["kv_cache"]
cols = 4
for i in range(sram_blocks):
    cx = kx0 + 0.01*W + (i % cols) * (sb * 1.15)
    cy = ky0 + 0.01*W + (i // cols) * (sb * 1.15)
    rect(cx, cy, cx + sb, cy + sb, layer=101)

# 逻辑模块块
for feat, r in regions.items():
    if feat == "kv_cache":
        continue  # 已被 SRAM 宏占位
    x0, y0, x1, y1 = r
    if feat == "other":
        x0, y0, x1, y1 = 0.10*W, 0.10*W, 0.90*W, 0.28*W  # 下方条带
    rect(x0, y0, x1, y1, layer=200)

# 标签
cell.add(gdspy.Text("Vortex GPGPU floorplan (Nangate45, synth-area based)", 30, (0.02*W*1000, (W-0.05)*1000), layer=100))
for feat, r in regions.items():
    x0, y0, x1, y1 = r
    cell.add(gdspy.Text(f"{feat}: {groups[feat]['area']/1e6:.2f}mm2", 20, (x0*1000+10, y0*1000+10), layer=100))

os.makedirs(f"{BUILD}/out", exist_ok=True)
lib.write_gds(f"{BUILD}/out/floorplan.gds")
print(f"GDS 已写出: {BUILD}/out/floorplan.gds")

# ---- 6. 文本版图 (终端直看) ----
print("\n===== 版图示意图 (mm) =====")
N = 28
grid = [["."] * N for _ in range(14)]
def draw(x0, y0, x1, y1, ch):
    for gy in range(int(y0/W*14), min(14, max(int(y0/W*14)+1, int(y1/W*14)))):
        for gx in range(int(x0/W*N), min(N, max(int(x0/W*N)+1, int(x1/W*N)))):
            grid[gy][gx] = ch
draw(0, 0, W, W, "#")                      # die 边界
for feat, r in regions.items():
    if feat == "kv_cache":
        for i in range(16):
            cx = kx0 + 0.01*W + (i % cols) * (sb * 1.15)
            cy = ky0 + 0.01*W + (i // cols) * (sb * 1.15)
            draw(cx, cy, cx+sb, cy+sb, "K")
    else:
        x0, y0, x1, y1 = r
        if feat == "other":
            x0, y0, x1, y1 = 0.10*W, 0.10*W, 0.90*W, 0.28*W
        draw(x0, y0, x1, y1, feat[0].upper())
for row in grid:
    print("".join(row))
print("K=KV cache SRAM宏  Q=QKV GEMM/FMA  M=MoE NoC  T=AXI/HBM PHY  O=其余逻辑")

# ---- 7. PNG 渲染 (SVG 版) ----
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="900" viewBox="0 0 {W*1000} {W*1000}">',
       f'<rect x="0" y="0" width="{W*1000}" height="{W*1000}" fill="#111827" stroke="#6B7280" stroke-width="6"/>']
for feat, r in regions.items():
    x0, y0, x1, y1 = r
    if feat == "other":
        x0, y0, x1, y1 = 0.10*W, 0.10*W, 0.90*W, 0.28*W
    c = COLORS[feat]
    svg.append(f'<rect x="{x0*1000}" y="{y0*1000}" width="{(x1-x0)*1000}" height="{(y1-y0)*1000}" fill="{c}" fill-opacity="0.35" stroke="{c}" stroke-width="4"/>')
    svg.append(f'<text x="{x0*1000+20}" y="{y0*1000+40}" fill="#F9FAFB" font-size="34" font-family="Menlo">{feat}  {groups[feat]["area"]/1e6:.2f}mm²</text>')
for i in range(sram_blocks):
    cx = kx0 + 0.01*W + (i % cols) * (sb * 1.15)
    cy = ky0 + 0.01*W + (i // cols) * (sb * 1.15)
    svg.append(f'<rect x="{cx*1000}" y="{cy*1000}" width="{sb*1000}" height="{sb*1000}" fill="{COLORS["sram"]}" fill-opacity="0.9" stroke="#93C5FD" stroke-width="2"/>')
svg.append(f'<text x="{(0.02*W)*1000}" y="{(W-0.03)*1000}" fill="#F9FAFB" font-size="30" font-family="Menlo">Vortex GPGPU Floorplan — Nangate45, 基于实测综合面积 (std {total_std/1e6:.2f}mm² + SRAM {sram/1e6:.3f}mm²)</text>')
svg.append('</svg>')
with open(f"{BUILD}/out/floorplan.svg", "w") as f:
    f.write("\n".join(svg))
print(f"SVG 已写出: {BUILD}/out/floorplan.svg")
