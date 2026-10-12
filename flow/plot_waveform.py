#!/usr/bin/env python3
# =============================================================
# VCD → 波形图 SVG（零第三方依赖）
#
# 把仿真波形（VCD）渲染成浏览器 / GitHub 可直接查看的 SVG，
# 不需要 gtkwave，也不需要 matplotlib。
#
# 用法：
#   python3 flow/plot_waveform.py sim.vcd -o wave.svg
#   python3 flow/plot_waveform.py sim.vcd -o wave.svg --signals clk,scan_en,scan_out
#   python3 flow/plot_waveform.py sim.vcd -o wave.svg --title "扫描链移位"
#
# 支持：数字信号（0/1/x/z）阶梯波形、多 bit 总线（十六进制取值）、
#       时间轴刻度、信号名与位宽标注。
# =============================================================
from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

ROW_H = 30          # 单 bit 信号行高
BUS_H = 40          # 总线行高
LABEL_W = 190       # 左侧信号名区宽度
PAD_T = 52          # 顶部留白（标题 + 时间刻度）
PAD_B = 34          # 底部留白（时间轴）
PAD_R = 24


def parse_vcd(path: Path):
    """返回 (timescale, signals, changes)。

    signals: [(vid, width, name)] 按声明顺序
    changes: {vid: [(time, value)]}，value 为 '0'/'1'/'x'/'z' 或 'b<二进制>' 的二进制串
    """
    signals: list[tuple[str, int, str]] = []
    changes: dict[str, list[tuple[int, str]]] = {}
    timescale = "1ns"
    cur = 0

    with path.open(encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("$timescale"):
                body = line[len("$timescale"):].replace("$end", "").strip()
                if body:
                    timescale = body
                continue
            if line.startswith("$var"):
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        width = int(parts[2])
                    except ValueError:
                        continue
                    vid, name = parts[3], parts[4]
                    signals.append((vid, width, name))
                    changes.setdefault(vid, [])
                continue
            if line.startswith("$"):
                continue
            if line.startswith("#"):
                try:
                    cur = int(line[1:])
                except ValueError:
                    pass
                continue
            head = line[0]
            if head in "01xzXZ":
                changes.setdefault(line[1:], []).append((cur, head.lower()))
            elif head in "bB":
                val, _, vid = line.partition(" ")
                if vid:
                    changes.setdefault(vid, []).append((cur, val[1:].lower()))
    return timescale, signals, changes


def segments(events: list[tuple[int, str]], tmax: int):
    """把值变化点展开成 (t_start, t_end, value) 区段列表。"""
    if not events:
        return [(0, tmax, "x")]
    segs = []
    if events[0][0] > 0:
        segs.append((0, events[0][0], "x"))
    for i, (t, v) in enumerate(events):
        end = events[i + 1][0] if i + 1 < len(events) else tmax
        if end > t:
            segs.append((t, end, v))
    return segs


def hexval(bits: str, width: int) -> str:
    """总线取值显示：x/z 原样，其余按位宽转十六进制。"""
    if set(bits) <= {"x"}:
        return "x"
    if set(bits) <= {"z"}:
        return "z"
    if "x" in bits or "z" in bits:
        return "x/z"
    try:
        n = int(bits, 2)
    except ValueError:
        return bits
    digits = max(1, (width + 3) // 4)
    return f"{n:0{digits}X}"


def render(signals, changes, tmax, timescale, title, out: Path, ticks: int = 10):
    rows = []
    y = PAD_T
    for vid, width, name in signals:
        h = BUS_H if width > 1 else ROW_H
        rows.append((vid, width, name, y, h))
        y += h
    body_h = y - PAD_T
    total_h = PAD_T + body_h + PAD_B
    total_w = 1280
    plot_w = total_w - LABEL_W - PAD_R
    tmax = max(tmax, 1)

    def x_of(t: float) -> float:
        return LABEL_W + (t / tmax) * plot_w

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}" '
        f'viewBox="0 0 {total_w} {total_h}" font-family="Menlo,Consolas,monospace">',
        f'<rect width="{total_w}" height="{total_h}" fill="#fbfbfd"/>',
    ]
    if title:
        svg.append(
            f'<text x="{LABEL_W}" y="26" font-size="16" font-weight="600" fill="#111">'
            f'{html.escape(title)}</text>'
        )
    svg.append(
        f'<text x="{LABEL_W}" y="43" font-size="11" fill="#777">'
        f'timescale {html.escape(timescale)} · 0 – {tmax}</text>'
    )

    # 时间网格与刻度
    for i in range(ticks + 1):
        t = tmax * i / ticks
        x = x_of(t)
        svg.append(
            f'<line x1="{x:.1f}" y1="{PAD_T - 8}" x2="{x:.1f}" y2="{PAD_T + body_h}" '
            f'stroke="#e6e6ee" stroke-width="1"/>'
        )
        svg.append(
            f'<text x="{x:.1f}" y="{PAD_T + body_h + 18}" font-size="10" fill="#888" '
            f'text-anchor="middle">{t:.0f}</text>'
        )

    # 信号名区
    svg.append(
        f'<rect x="0" y="{PAD_T - 8}" width="{LABEL_W}" height="{body_h + 8}" fill="#f2f2f7"/>'
    )

    for vid, width, name, ry, rh in rows:
        mid = ry + rh / 2
        segs = segments(changes.get(vid, []), tmax)
        svg.append(
            f'<text x="{LABEL_W - 12}" y="{mid + 4:.1f}" font-size="12" fill="#222" '
            f'text-anchor="end">{html.escape(name)}'
            + (f' <tspan fill="#999">[{width - 1}:0]</tspan>' if width > 1 else "")
            + "</text>"
        )
        svg.append(
            f'<line x1="0" y1="{ry + rh:.1f}" x2="{LABEL_W + plot_w}" y2="{ry + rh:.1f}" '
            f'stroke="#e0e0e8" stroke-width="1"/>'
        )
        if width > 1:
            for t0, t1, v in segs:
                x0, x1 = x_of(t0), x_of(t1)
                if x1 - x0 < 0.6:
                    continue
                label = hexval(v, width)
                invalid = label in ("x", "z", "x/z")
                svg.append(
                    f'<rect x="{x0:.1f}" y="{ry + 6:.1f}" width="{x1 - x0:.1f}" '
                    f'height="{rh - 14:.1f}" fill="{"#f0f0f4" if invalid else "#dbe8ff"}" '
                    f'stroke="#5b7fc7" stroke-width="1"/>'
                )
                svg.append(
                    f'<text x="{(x0 + x1) / 2:.1f}" y="{mid + 4:.1f}" font-size="11" '
                    f'fill="#1f3d73" text-anchor="middle">{label}</text>'
                )
        else:
            y_hi, y_lo = ry + 8, ry + rh - 10
            prev_x, prev_y = None, None
            for t0, t1, v in segs:
                x0, x1 = x_of(t0), x_of(t1)
                if v in ("0",):
                    y0 = y1 = y_lo
                elif v in ("1",):
                    y0 = y1 = y_hi
                else:  # x / z 画中线并用灰色表示未知
                    y0 = y1 = mid
                if prev_x is None:
                    svg.append(
                        f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y0:.1f}" '
                        f'stroke="{"#bbb" if v in ("x", "z") else "#1a6bd6"}" stroke-width="2"/>'
                    )
                else:
                    col = "#bbb" if v in ("x", "z") else "#1a6bd6"
                    svg.append(
                        f'<polyline points="{prev_x:.1f},{prev_y:.1f} {x0:.1f},{prev_y:.1f} '
                        f'{x0:.1f},{y0:.1f} {x1:.1f},{y0:.1f}" fill="none" stroke="{col}" '
                        f'stroke-width="2"/>'
                    )
                prev_x, prev_y = x1, y0

    svg.append("</svg>")
    out.write_text("\n".join(svg) + "\n", encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="VCD → 波形 SVG（零依赖）")
    ap.add_argument("vcd", type=Path, help="输入 VCD 文件")
    ap.add_argument("-o", "--out", type=Path, required=True, help="输出 SVG 路径")
    ap.add_argument("--title", default="", help="图标题")
    ap.add_argument("--signals", default="", help="只画这些信号（逗号分隔，默认全部）")
    ap.add_argument("--ticks", type=int, default=10, help="时间轴刻度数")
    args = ap.parse_args(argv)

    if not args.vcd.is_file():
        print(f"找不到 VCD: {args.vcd}", file=sys.stderr)
        return 1

    timescale, signals, changes = parse_vcd(args.vcd)
    if not signals:
        print("VCD 里没有 $var 声明，无法绘图", file=sys.stderr)
        return 1

    want = [s.strip() for s in args.signals.split(",") if s.strip()]
    seen = set()
    picked = []
    for vid, width, name in signals:
        if want and name not in want:
            continue
        if name in seen:  # tb 与其子模块共享同一根线，重名只画一次
            continue
        seen.add(name)
        picked.append((vid, width, name))
    signals = picked

    tmax = 0
    for vid, events in changes.items():
        for t, _ in events:
            tmax = max(tmax, t)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    render(signals, changes, tmax, timescale, args.title, args.out, args.ticks)
    print(f"已写出 {args.out}（{len(signals)} 个信号，时间轴 0–{tmax}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
