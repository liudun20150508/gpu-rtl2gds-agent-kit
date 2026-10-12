#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把综合网表中每一个真实标准单元摆成版图 (row-based 摆放, 无布线)

输入: Vortex_mapped.v (281,881 个真实门级实例) + NangateOpenCellLibrary.macro.lef (真实单元尺寸)
输出: layout_cells.gds (每个门一个矩形, 模块聚簇, 负载特征着色) + layout_cells.png
说明: 这是"摆放"不是"布线"——金属走线由 OpenROAD 在 Linux 上完成,
      但图上每一个格子都是综合网表里真实存在的一个标准单元。
"""
import re, os, sys, math
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import gdspy
from llm_eda.netlist_bind import BINDING
from collections import defaultdict

BUILD = os.path.join(ROOT, "build/vortex_base")
NETLIST = f"{BUILD}/out/Vortex_mapped.v"
LEF = os.path.join(ROOT, "pdks/nangate45/lef/NangateOpenCellLibrary.macro.lef")

# ---- 1. LEF 单元真实尺寸 ----
lef = open(LEF, encoding="utf-8", errors="ignore").read()
sizes = {}
for m in re.finditer(r"MACRO\s+(\S+).*?SIZE\s+([\d.]+)\s+BY\s+([\d.]+)", lef, re.S):
    sizes[m.group(1)] = (float(m.group(2)), float(m.group(3)))
site_h = 1.4  # FreePDK45 site 高度 (um), 行高
site_w = 0.19
print(f"LEF 解析: {len(sizes)} 个单元")

# ---- 2. 网表实例解析 (inst -> cell type) + 所属模块 ----
instances = []
cur_mod = None
for line in open(NETLIST, encoding="utf-8", errors="ignore"):
    ls = line.rstrip()
    mm = re.match(r"\s*module\s+(\S+)", ls)
    if mm:
        cur_mod = mm.group(1).replace("\\", "")
        continue
    mm = re.match(r"\s*([A-Z][A-Z0-9]*_X\d+)\s+(\\?[^ (]+)", ls)
    if mm and cur_mod:
        instances.append((mm.group(1), cur_mod))
print(f"网表解析: {len(instances)} 个标准单元实例")

# ---- 3. 模块 -> 负载特征分类 ----
def feat_of(mod):
    for feat, spec in BINDING.items():
        for m in spec["modules"]:
            if m in mod:
                return feat
    return "other"

FEAT_COLORS = {"kv_cache": 101, "qkv_gemm": 102, "moe_noc": 103,
               "tp_hbm": 104, "other": 105, "sram": 106}
by_feat = defaultdict(list)
for t, mod in instances:
    by_feat[feat_of(mod)].append((t, mod))

# ---- 4. 面积 -> die 尺寸 ----
total_inst_area = sum(sizes.get(t, (0.95, 1.4))[0] * site_h for t, _ in instances)
sram_area = 57079.2
util = 0.72
die_area = (total_inst_area + sram_area) / util
W = die_area ** 0.5
print(f"单元总面积 {total_inst_area:.0f} um^2 + SRAM {sram_area:.0f} -> die {W:.0f} x {W:.0f} um")

# ---- 5. 行摆放 (模块聚簇: 特征块从下往上) ----
FEAT_ORDER = ["kv_cache", "qkv_gemm", "moe_noc", "tp_hbm", "other"]
margin = 20.0
x_cur, y_cur = margin, margin
placed = []

def new_row_if_needed(w):
    global x_cur, y_cur
    if x_cur + w > W - margin:
        x_cur = margin
        y_cur += site_h

# SRAM 宏: 16 块大矩形放最底
sram_blocks = 16
sb = (sram_area / sram_blocks) ** 0.5
cols = 4
for i in range(sram_blocks):
    cx = margin + (i % cols) * (sb + 5)
    cy = margin + (i // cols) * (sb + 5)
    placed.append(("SRAM", cx, cy, FEAT_COLORS["sram"], sb, sb))
y_cur = margin + 4 * (sb + 5) + 10

for feat in FEAT_ORDER:
    cells = by_feat.get(feat, [])
    cells.sort(key=lambda c: c[1])
    for t, mod in cells:
        w_cell = sizes.get(t, (0.95, 1.4))[0]
        w = max(w_cell, site_w)
        new_row_if_needed(w)
        placed.append((t, x_cur, y_cur, FEAT_COLORS[feat], w, site_h))
        x_cur += w

print(f"摆放完成: {len(placed)} 个对象 (含 {sram_blocks} SRAM 宏)")

# ---- 6. GDS 写出 ----
lib = gdspy.GdsLibrary(name="VortexCellLayout", unit=1e-6, precision=1e-9)
cell = lib.new_cell("Vortex_CELLS")
cell.add(gdspy.Rectangle((0, 0), (W, W), layer=100))
for item in placed:
    t, x, y, layer, w, h = item
    cell.add(gdspy.Rectangle((x, y), (x + w, y + h), layer=layer))
# 电源轨 (每行 VDD/VSS 示意)
for yy in [margin + i * site_h for i in range(int((y_cur - margin) / site_h) + 1)]:
    cell.add(gdspy.Rectangle((margin, yy + site_h - 0.2), (W - margin, yy + site_h), layer=110))
os.makedirs(f"{BUILD}/out", exist_ok=True)
lib.write_gds(f"{BUILD}/out/layout_cells.gds")
print(f"GDS: {BUILD}/out/layout_cells.gds ({len(placed)} 对象)")

# ---- 7. PNG 渲染 (Pillow, 着色) ----
try:
    from PIL import Image, ImageDraw
    SCALE = 5000 / W
    img = Image.new("RGB", (5000, 5000), (17, 24, 39))
    d = ImageDraw.Draw(img)
    PALETTE = {101: (59, 130, 246), 102: (239, 68, 68), 103: (16, 185, 129),
               104: (245, 158, 11), 105: (156, 163, 175), 106: (29, 78, 216),
               110: (255, 200, 0)}
    for item in placed:
        t, x, y, layer, w, h = item
        c = PALETTE.get(layer, (255, 255, 255))
        x0, y0 = int(x * SCALE), int(y * SCALE)
        x1, y1 = int((x + w) * SCALE), int((y + h) * SCALE)
        if x1 <= x0: x1 = x0 + 1
        if y1 <= y0: y1 = y0 + 1
        d.rectangle([x0, y0, x1, y1], fill=c)
    img.save(f"{BUILD}/out/layout_cells.png")
    print(f"PNG: {BUILD}/out/layout_cells.png (5000x5000)")
except ImportError:
    print("Pillow 未安装, 跳过 PNG (pip3 install pillow)")

# ---- 8. 统计 ----
feat_stat = defaultdict(int)
for t, x, y, layer, w, h in placed:
    feat_stat[layer] += 1
print("层统计: SRAM=%d kv=%d qkv=%d noc=%d io=%d other=%d" % (
    feat_stat[106], feat_stat[101], feat_stat[102], feat_stat[103], feat_stat[104], feat_stat[105]))
