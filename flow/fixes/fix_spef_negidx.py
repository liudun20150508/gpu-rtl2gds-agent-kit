#!/usr/bin/env python3
r"""修复 OpenRCX SPEF 的 [\-N] 毒 token（STA-1670）。

## 现象
STA 阶段 `read_spef` 报 `[ERROR STA-1670] ... syntax error`。
base 版 Vortex SKY130 在 line 502796 报错，TCU 版在 line 503671（同构）。

## 根因
OpenRCX 的 SPEF writer 把负索引总线名写成 `mem_req_addr[\-1]`：
  * `[0]` 这类正常索引 OpenSTA 能容忍，87 万行里绝大多数都属于这种；
  * 致命的是 `[\-1]` 里的反斜杠 —— 词法器在 bus index 里遇到转义符即报 syntax error。
实测：`\[-1\]`（括号转义 + 去掉减号前的反斜杠）可以过；
      `\[\-1\]`（直觉修法）**依然报错**，别用。

## 规模（base 版实测）
789MB SPEF 中 `[\-N]` 仅 63 处（name map 63 行，PORTS/D_NET 引用随之替换）。
修复后 21,877,246 行全量解析通过（exit 0）。

## 用法
    python3 fix_spef_negidx.py --check   <in.spef>             # 只数有多少处，不改文件
    python3 fix_spef_negidx.py           <in.spef> <out.spef>  # 写出修复后的 SPEF
    python3 fix_spef_negidx.py --selftest                      # 内置样例自检

修完只需重跑 6_report（read_spef 新文件 + report_timing），不必重跑布线与寄生提取。

## 注意
本文件 docstring 必须是 raw string（`r` 前缀）。普通字符串里的 `\[` 会被当成未知转义序列，
Python 3.12+ 会往 stderr 发 SyntaxWarning；而流程脚本用 Tcl `exec` 调这个脚本时，
stderr 上的任何输出都会被当成执行失败。改动本文件时不要"顺手"把 r 去掉。
"""

import re
import sys

#: [\-1] [\-9] ...（减号前带反斜杠的负索引）
PAT = re.compile(r'\[(\\-(\d+))\]')

SAMPLE_BAD = "mem_req_addr[\\-1] : net1\nmem_req_addr[0] : net0\nD_NET mem_req_addr[\\-2] 0.1\n"
SAMPLE_GOOD = "mem_req_addr\\[-1\\] : net1\nmem_req_addr[0] : net0\nD_NET mem_req_addr\\[-2\\] 0.1\n"


def convert_line(line):
    """返回 (新行, 本行替换处数)。不含毒 token 的行原样返回。"""
    if '\\-' in line and '[' in line:
        return PAT.subn(r'\[-\2\]', line)
    return line, 0


def run(src, dst=None):
    """扫一遍 src。dst 为 None 时只统计（--check），否则写出修复后的内容。"""
    n = 0
    out = open(dst, 'w') if dst else None
    try:
        with open(src, 'r', errors='replace') as fin:
            for line in fin:
                line, k = convert_line(line)
                n += k
                if out is not None:
                    out.write(line)
    finally:
        if out is not None:
            out.close()
    return n


def selftest():
    fixed, n = convert_line(SAMPLE_BAD)
    ok = True
    if n != 2:
        print("  ✗ 样例应替换 2 处，实际 %d 处" % n)
        ok = False
    else:
        print("  ✓ 样例替换 2 处")
    if fixed != SAMPLE_GOOD:
        print("  ✗ 替换结果与预期不符\n    实际: %r\n    预期: %r" % (fixed, SAMPLE_GOOD))
        ok = False
    else:
        print("  ✓ 替换形态正确：\\[-1\\]（括号转义 + 去掉减号前反斜杠）")
    if '[\\-1]' not in fixed and '\\[-1\\]' in fixed:
        print("  ✓ 未修复形态 [\\-1] 已消失，规范写法 \\[-1\\] 已生成")
    else:
        print("  ✗ 替换形态不对：仍残留毒 token，或没生成规范写法")
        ok = False
    # 正常索引必须原样保留
    if "mem_req_addr[0] : net0" in fixed:
        print("  ✓ 正常索引 [0] 未被改动")
    else:
        print("  ✗ 正常索引被误改")
        ok = False
    print()
    print("自检通过。" if ok else "自检失败。")
    return 0 if ok else 1


def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0 if argv else 2
    if argv[0] == '--selftest':
        return selftest()
    if argv[0] == '--check':
        if len(argv) != 2:
            print("用法: fix_spef_negidx.py --check <in.spef>", file=sys.stderr)
            return 2
        n = run(argv[1])
        print("毒 token [\\-N] 共 %d 处 —— %s" % (n, "需要修复" if n else "无需修复"))
        return 0 if n == 0 else 1
    if len(argv) != 2:
        print("用法: fix_spef_negidx.py <in.spef> <out.spef>", file=sys.stderr)
        return 2
    n = run(argv[0], argv[1])
    print("fixed lines: %d" % n)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
