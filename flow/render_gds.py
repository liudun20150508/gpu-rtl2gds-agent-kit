#!/usr/bin/env python3
"""渲染最终 GDS 版图 (KLayout Python 绑定, 需 ~/bin/klayout 的 python 环境)

用法: $HOME/bin/klayout -b -r flow/render_gds.py <gds> <out.png> [zoom_px]
"""
import pya, sys, os
gds = sys.argv[1] if len(sys.argv) > 1 else ""
out = sys.argv[2] if len(sys.argv) > 2 else ""
zoom = int(sys.argv[3]) if len(sys.argv) > 3 else 0
if not gds:
    gds = os.path.expanduser(os.environ.get("ORFS_ROOT", "~/tools/OpenROAD-flow-scripts/flow") + "/results/sky130hd/vortex/base/6_final.gds")
if not out:
    out = "layout_final.png"
lv = pya.LayoutView()
lv.load_layout(gds, True)
lv.max_hier()
lv.zoom_fit()
if zoom > 0:
    lv.zoom_box()
lv.save_image(out, 3200, 2400)
print("rendered:", gds, "->", out)
