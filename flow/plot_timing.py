#!/usr/bin/env python3
# =============================================================
# 时序指标 → 时序图 SVG（零第三方依赖）
#
# 读一份 CSV（每次迭代/每个配置一行），画：
#   ① WNS 时序裕量条形图（含 0 基线，正值为裕量、负值为违规）
#   ② 门数规模条形图
# 输出可直接在浏览器 / GitHub 查看的 SVG。
#
# 输入 CSV 列（表头必需）：
#   name,wns_ns   必需
#   tns_ns,period_ns,freq_mhz,gates,violations   可选
#
# 用法：
#   python3 flow/plot_timing.py examples/timing/three_variants.csv -o timing.svg
#   python3 flow/plot_timing.py iter.csv -o trend.svg --title "闭环迭代收敛"
# =============================================================
from __future__ import annotations

import argparse
import csv
import html
import sys
from pathlib import Path

W = 1160
BAR_H = 34
GAP = 16
PAD_L = 190
PAD_R = 90
PANEL_TITLE = 26


def _load(path: Path):
    rows = []
    with path.open(encoding="utf-8", newline="") as fh:
        for raw in csv.DictReader(fh):
            name = (raw.get("name") or "").strip()
            if not name:
                continue
            rec = {"name": name}

            def num(key):
                v = (raw.get(key) or "").strip()
                if not v:
                    return None
                try:
                    return float(v)
                except ValueError:
                    return None

            rec["wns_ns"] = num("wns_ns")
            rec["tns_ns"] = num("tns_ns")
            rec["freq_mhz"] = num("freq_mhz")
            rec["gates"] = num("gates")
            rec["violations"] = num("violations")
            rows.append(rec)
    return rows


def _bar_panel(svg, rows, key, title, y0, unit, better_high=True, color_ok="#2f7d32",
               color_bad="#c62828", color_bar="#4a7fd4"):
    """画一个条形图面板，返回面板底部 y。"""
    vals = [r[key] for r in rows if r.get(key) is not None]
    svg.append(
        f'<text x="{PAD_L}" y="{y0}" font-size="15" font-weight="600" fill="#111">'
        f'{html.escape(title)}</text>'
    )
    top = y0 + PANEL_TITLE
    if not vals:
        svg.append(
            f'<text x="{PAD_L}" y="{top + 18}" font-size="12" fill="#999">'
            f'（CSV 中没有 {key} 列）</text>'
        )
        return top + 44

    vmax = max(vals)
    vmin = min(vals)
    lo = min(0.0, vmin)
    hi = max(vmax, 0.0)
    if hi == lo:
        hi = lo + 1.0
    span = hi - lo

    plot_w = W - PAD_L - PAD_R

    def x_of(v):
        return PAD_L + (v - lo) / span * plot_w

    # 0 基线
    xz = x_of(0.0)
    svg.append(
        f'<line x1="{xz:.1f}" y1="{top - 6}" x2="{xz:.1f}" '
        f'y2="{top + len(rows) * (BAR_H + GAP) + 4}" stroke="#999" stroke-width="1.5"/>'
    )

    y = top
    for r in rows:
        v = r.get(key)
        svg.append(
            f'<text x="{PAD_L - 14}" y="{y + BAR_H / 2 + 4:.1f}" font-size="12" '
            f'fill="#222" text-anchor="end">{html.escape(r["name"])}</text>'
        )
        if v is None:
            svg.append(
                f'<text x="{xz + 8:.1f}" y="{y + BAR_H / 2 + 4:.1f}" font-size="11" '
                f'fill="#999">n/a</text>'
            )
        else:
            x0, x1 = (xz, x_of(v)) if v >= 0 else (x_of(v), xz)
            good = (v >= 0) if better_high else (v <= 0)
            fill = color_bar if key != "wns_ns" else (color_ok if good else color_bad)
            svg.append(
                f'<rect x="{x0:.1f}" y="{y + 5:.1f}" width="{max(x1 - x0, 1.5):.1f}" '
                f'height="{BAR_H - 10}" fill="{fill}" rx="2"/>'
            )
            tx = x1 + 8 if v >= 0 else x0 - 8
            anchor = "start" if v >= 0 else "end"
            svg.append(
                f'<text x="{tx:.1f}" y="{y + BAR_H / 2 + 4:.1f}" font-size="12" '
                f'fill="#333" text-anchor="{anchor}">{v:g}{html.escape(unit)}</text>'
            )
        y += BAR_H + GAP
        svg.append(
            f'<line x1="{PAD_L}" y1="{y - GAP / 2:.1f}" x2="{W - PAD_R}" '
            f'y2="{y - GAP / 2:.1f}" stroke="#eee" stroke-width="1"/>'
        )
    return y


def render(rows, title, out: Path):
    n_wns = len(rows)
    h = 150 + n_wns * (BAR_H + GAP) + 40 + n_wns * (BAR_H + GAP) + 70
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" '
        f'viewBox="0 0 {W} {h}" font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif">',
        f'<rect width="{W}" height="{h}" fill="#fbfbfd"/>',
        f'<text x="24" y="34" font-size="18" font-weight="700" fill="#111">'
        f'{html.escape(title)}</text>',
    ]
    y = 74
    y = _bar_panel(svg, rows, "wns_ns", "时序裕量 WNS（ns，越正越好；&lt;0 为违规）", y, " ns")
    y += 24
    y = _bar_panel(svg, rows, "gates", "规模：标准单元/门数", y, "", color_bar="#7a5af8")
    svg.append(
        f'<text x="24" y="{h - 18}" font-size="11" fill="#999">'
        f'由 flow/plot_timing.py 生成 · 数据源 CSV</text>'
    )
    svg.append("</svg>")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(svg) + "\n", encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="时序指标 CSV → SVG")
    ap.add_argument("csv", type=Path, help="输入 CSV")
    ap.add_argument("-o", "--out", type=Path, required=True, help="输出 SVG")
    ap.add_argument("--title", default="时序裕量与规模对比", help="图标题")
    args = ap.parse_args(argv)

    if not args.csv.is_file():
        print(f"找不到 CSV: {args.csv}", file=sys.stderr)
        return 1
    rows = _load(args.csv)
    if not rows:
        print("CSV 无有效数据行（需要 name,wns_ns 表头）", file=sys.stderr)
        return 1
    render(rows, args.title, args.out)
    print(f"已写出 {args.out}（{len(rows)} 行数据）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
