#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""双库策略：从原始 .lib 生成 dffmap 库与 patched 库（修复 DFF legalize 失败）。

## 为什么需要两份库

yosys 的 dfflibmap 与 abc / OpenSTA 对触发器 Q 引脚 `function` 的要求互相冲突：

  * **dfflibmap** 要 Q 引脚 `function` 为 `IQ` / `IQ_N`，且 ff 组里带 clear/preset，
    才能把 $_DFF_PP_ / $_DFFE_PP_ 这类内部触发器映射到具体标准单元；
  * **abc / OpenSTA** 解析时要求 Q 引脚 `function` 为 `D` / `!D`，遇到 `IQ` 会解析失败，
    典型报错是 `$_DFFE_PP_ cannot be legalized`。

一份库无法同时满足，所以综合流程里同时喂两份（见 `flow/02_synth_sky130.sh`
的 `LIB_DFFMAP` / `LIB` 两个变量）：

    read_liberty -lib <dffmap 库>     # 只给 dfflibmap 用
    read_liberty      <patched 库>    # 给 abc / 时序分析用

## 用法

    python3 gen_dff_libs.py --inspect  <原始.lib>              # 只报告，不改任何东西
    python3 gen_dff_libs.py --apply    <原始.lib> <输出目录>
    python3 gen_dff_libs.py --check    <输出目录> [库文件名前缀]
    python3 gen_dff_libs.py --selftest                         # 用内置样例验证变换逻辑

**先跑 `--inspect`**：它会报出库里有多少单元、每个 Q 引脚的 function 当前是什么值、
ff 组里有没有 clear/preset。若输出与下面的假定对不上，说明你这版库结构不同，
改本文件顶部的规则再跑，不要直接 --apply。

输出文件名与流程脚本的约定一致：`<stem>_dffmap.lib` 与 `<stem>_patched.lib`，
其中 stem 是输入文件名去掉 `.lib`。例如输入
`sky130_fd_sc_hd__tt_025C_1v80.lib` 会产出
`sky130_fd_sc_hd__tt_025C_1v80_dffmap.lib` 和 `..._patched.lib`。
"""

from __future__ import annotations

import argparse
import os
import re
import sys

# ---------------------------------------------------------------- 规则定义

#: 会被本脚本接管的 Q / Q_N 引脚 function 取值。其它取值一律不动。
DFF_FUNCS = {"IQ", "IQ_N", "D", "!D"}

#: 低有效复位/置位引脚名 → 写进 ff 组的字段与取值。
#  liberty 语义：低有效复位写 `clear : "!RESET_B"`，低有效置位写 `preset : "!SET_B"`。
CLEAR_PIN = "RESET_B"
PRESET_PIN = "SET_B"

FUNC_RE = re.compile(r'(\bfunction\s*:\s*")([^"]*)(")')
FF_RE = re.compile(r'\bff\s*\([^)]*\)\s*\{')

# ---------------------------------------------------------------- 结构解析


def sub_blocks(text: str, kind: str):
    """找出所有 `kind (name) { ... }` 块，按括号配平，不依赖缩进风格。

    返回 [(name, start, end, body)]，start/end 是在 text 中的绝对偏移。
    """
    out = []
    pat = re.compile(r'\b%s\s*\(\s*"?([A-Za-z0-9_]+)"?\s*\)\s*\{' % re.escape(kind))
    for m in pat.finditer(text):
        depth = 0
        for j in range(m.end() - 1, len(text)):
            c = text[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    out.append((m.group(1), m.start(), j + 1, text[m.start():j + 1]))
                    break
    return out


def cells(text: str):
    return sub_blocks(text, "cell")


def has_pin(cell_body: str, pin: str) -> bool:
    return re.search(r'\bpin\s*\(\s*"?%s"?\s*\)' % re.escape(pin), cell_body) is not None


def ff_fields(cell_body: str):
    """返回 ff 组里已出现的字段名集合。"""
    m = FF_RE.search(cell_body)
    if not m:
        return set(), None
    depth = 0
    for j in range(m.end() - 1, len(cell_body)):
        c = cell_body[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                body = cell_body[m.end():j]
                return set(re.findall(r'(\w+)\s*:', body)), m.end()
    return set(), m.end()


# ---------------------------------------------------------------- 变换


def patch(text: str, mode: str):
    """按 mode（dffmap / patched）变换库文本。返回 (新文本, 改动条数, 明细)。"""
    edits = []   # (start, end, new_text, 说明)
    notes = []

    for cname, cs, _ce, cbody in cells(text):
        # 1) Q / Q_N 引脚的 function
        for pname, ps, _pe, pbody in sub_blocks(cbody, "pin"):
            if pname not in ("Q", "Q_N"):
                continue
            m = FUNC_RE.search(pbody)
            if not m or m.group(2) not in DFF_FUNCS:
                continue
            old = m.group(2)
            want = ("IQ" if pname == "Q" else "IQ_N") if mode == "dffmap" else ("D" if pname == "Q" else "!D")
            if old == want:
                continue
            edits.append((cs + ps + m.start(2), cs + ps + m.end(2), want,
                          "%s.%s function %s → %s" % (cname, pname, old, want)))

        # 2) ff 组补 clear / preset（只有 dffmap 库需要）
        if mode == "dffmap":
            fields, insert_at = ff_fields(cbody)
            if insert_at is not None:
                add = []
                if "clear" not in fields and has_pin(cbody, CLEAR_PIN):
                    add.append('clear : "!%s" ;' % CLEAR_PIN)
                if "preset" not in fields and has_pin(cbody, PRESET_PIN):
                    add.append('preset : "!%s" ;' % PRESET_PIN)
                for line in add:
                    edits.append((cs + insert_at, cs + insert_at, "\n      " + line,
                                  "%s.ff 补 %s" % (cname, line.split(":")[0].strip())))

        # 3) 三态单元加 dont_use（只有 patched 库需要）
        if mode == "patched" and "three_state" in cbody and "dont_use" not in cbody:
            brace = cbody.find("{")
            edits.append((cs + brace + 1, cs + brace + 1, "\n    dont_use : true ;",
                          "%s 三态单元加 dont_use" % cname))

    for a, b, new, note in sorted(edits, key=lambda e: e[0], reverse=True):
        text = text[:a] + new + text[b:]
        notes.append(note)

    notes.reverse()   # 恢复文件内出现顺序，便于阅读
    return text, len(notes), notes


def inspect(text: str):
    cs = cells(text)
    funcs = {}
    dff_like = 0
    for cname, _s, _e, cbody in cs:
        for pname, _ps, _pe, pbody in sub_blocks(cbody, "pin"):
            if pname not in ("Q", "Q_N"):
                continue
            m = FUNC_RE.search(pbody)
            if not m:
                continue
            funcs.setdefault(m.group(2), []).append("%s.%s" % (cname, pname))
            if pname == "Q":
                dff_like += 1
    return cs, funcs, dff_like


# ---------------------------------------------------------------- 自检样例

SAMPLES = """library (selftest) {
  cell (sky130_fd_sc_hd__dfxtp_1) {
    ff (IQ, IQ_N) {
      next_state : "D" ;
      clocked_on : "CLK" ;
    }
    pin (CLK) { direction : input ; }
    pin (D) { direction : input ; }
    pin (Q) { direction : output ; function : "IQ" ; }
  }
  cell (sky130_fd_sc_hd__dfrtp_1) {
    ff (IQ, IQ_N) {
      next_state : "D" ;
      clocked_on : "CLK" ;
    }
    pin (RESET_B) { direction : input ; }
    pin (Q) { direction : output ; function : "IQ" ; }
  }
  cell (sky130_fd_sc_hd__ebufn_1) {
    three_state : "A" ;
    pin (A) { direction : input ; }
    pin (Z) { direction : output ; function : "A" ; }
  }
}
"""


def selftest() -> int:
    failures = []

    def check(name, cond, detail=""):
        print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else "  " + detail))
        if not cond:
            failures.append(name)

    print("--inspect 能读出结构：")
    cs, funcs, dff_like = inspect(SAMPLES)
    check("识别出 3 个 cell", len(cs) == 3, "实际 %d" % len(cs))
    check("识别出 2 个带 Q 的触发器", dff_like == 2, "实际 %d" % dff_like)
    check("Q function 统计到 IQ", "IQ" in funcs, str(list(funcs)))

    print("dffmap 变换：")
    dffmap, n, notes = patch(SAMPLES, "dffmap")
    check("Q function 保持 IQ（不改成 D）",
          'function : "IQ"' in dffmap and 'function : "D"' not in dffmap)
    check("dfrtp 的 ff 组补上 clear", 'clear : "!RESET_B"' in dffmap)
    check("无复位的 dfxtp 不补 clear",
          dffmap.count("clear :") == 1, "clear 出现 %d 次" % dffmap.count("clear :"))
    check("三态单元不动 dont_use", "dont_use" not in dffmap)
    check("幂等：再跑一遍 dffmap 不产生改动", patch(dffmap, "dffmap")[1] == 0)

    print("patched 变换：")
    patched, n2, _ = patch(SAMPLES, "patched")
    check("两个触发器的 Q function 都变成 D", patched.count('function : "D"') == 2,
          "实际 %d" % patched.count('function : "D"'))
    check("三态单元加 dont_use", "dont_use : true" in patched)
    check("patched 不补 clear", "clear :" not in patched)
    check("幂等：再跑一遍 patched 不产生改动", patch(patched, "patched")[1] == 0)

    print("双向可逆：")
    back = patch(patched, "dffmap")[0]
    check("patched → dffmap 能还原 IQ", 'function : "IQ"' in back)

    print()
    if failures:
        print("自检失败 %d 项：%s" % (len(failures), "；".join(failures)))
        return 1
    print("自检全部通过。")
    return 0


# ---------------------------------------------------------------- 命令行


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="双库策略：从原始 .lib 生成 dffmap 库与 patched 库",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--inspect", metavar="LIB", help="只报告库结构，不改任何文件")
    g.add_argument("--apply", nargs=2, metavar=("LIB", "OUTDIR"), help="生成两份库")
    g.add_argument("--check", nargs="+", metavar="ARG", help="检查输出目录里两份库是否自洽")
    g.add_argument("--selftest", action="store_true", help="用内置样例验证变换逻辑")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    if args.inspect:
        path = args.inspect
        if not os.path.isfile(path):
            print("找不到文件：%s" % path, file=sys.stderr)
            return 2
        text = open(path, encoding="utf-8", errors="replace").read()
        cs, funcs, dff_like = inspect(text)
        print("文件：%s（%.1f MB）" % (path, len(text) / 1e6))
        print("cell 总数：%d，其中带 Q 引脚的：%d" % (len(cs), dff_like))
        print("Q / Q_N 引脚 function 取值分布：")
        for val, who in sorted(funcs.items()):
            print("  %-6s %4d 处   例：%s" % (val, len(who), ", ".join(who[:3])))
        print()
        expect = {"IQ", "IQ_N"}
        unknown = set(funcs) - DFF_FUNCS
        if unknown:
            print("注意：出现了本脚本未接管的取值 %s，这些引脚不会被改动。" % sorted(unknown))
        if not (set(funcs) & expect):
            print("警告：没找到 IQ / IQ_N 形式的 Q function。")
            print("      这版库可能已经是 patched 形态，或结构与预期不同 —— 别直接 --apply。")
        else:
            print("结构与预期一致，可以 --apply。")
        return 0

    if args.apply:
        src, outdir = args.apply
        if not os.path.isfile(src):
            print("找不到文件：%s" % src, file=sys.stderr)
            return 2
        os.makedirs(outdir, exist_ok=True)
        text = open(src, encoding="utf-8", errors="replace").read()
        stem = os.path.basename(src)[:-4] if src.endswith(".lib") else os.path.basename(src)
        rc = 0
        for mode in ("dffmap", "patched"):
            out, n, notes = patch(text, mode)
            dst = os.path.join(outdir, "%s_%s.lib" % (stem, mode))
            with open(dst, "w", encoding="utf-8") as fh:
                fh.write(out)
            print("%-8s → %s（%d 处改动）" % (mode, dst, n))
            for note in notes[:10]:
                print("           %s" % note)
            if len(notes) > 10:
                print("           …另有 %d 处" % (len(notes) - 10))
            if n == 0:
                print("           警告：0 处改动，说明这份库的结构与脚本假定不符。")
                print("           先跑 --inspect 看清 Q 引脚 function 的实际取值。")
                rc = 1
        print()
        print("在综合脚本里引用：")
        print("  LIB_DFFMAP=%s/%s_dffmap.lib" % (outdir, stem))
        print("  LIB=%s/%s_patched.lib" % (outdir, stem))
        return rc

    if args.check:
        outdir = args.check[0]
        prefix = args.check[1] if len(args.check) > 1 else ""
        bad = 0
        for mode, want in (("dffmap", ("IQ", "IQ_N")), ("patched", ("D", "!D"))):
            hits = []
            if os.path.isdir(outdir):
                for fn in sorted(os.listdir(outdir)):
                    if fn.endswith("_%s.lib" % mode) and (not prefix or fn.startswith(prefix)):
                        hits.append(os.path.join(outdir, fn))
            if not hits:
                print("✗ %-8s 未找到 %s*_%s.lib" % (mode, prefix or "", mode))
                bad += 1
                continue
            for path in hits:
                cs, funcs, _ = inspect(open(path, encoding="utf-8", errors="replace").read())
                got = set(funcs)
                ok = bool(got & set(want))
                print("%s %-8s %s（%d cell，Q function：%s）"
                      % ("✓" if ok else "✗", mode, path, len(cs), sorted(got) or "无"))
                if not ok:
                    bad += 1
        if bad:
            print("\n有 %d 项不自洽。跑 --inspect <原始.lib> 对比结构。" % bad)
            return 1
        print("\n两份库都自洽。")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
