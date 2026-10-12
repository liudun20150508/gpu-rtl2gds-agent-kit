#!/usr/bin/env python3
r"""修复 OpenRCX SPEF 的 [\-N] 毒token (STA-1670):
   mem_req_addr[\-1]  ->  mem_req_addr\[-1\]
原理: OpenSTA 词法器把 \[ 当转义左括号, \-1 里的反斜杠导致 bus index 解析失败;
       [0] 之类正常索引无需转义也能解析, 但 \[-N\] 是规范且安全的写法。
用法: fix_spef_negidx.py <in.spef> <out.spef>
"""
import re, sys

src, dst = sys.argv[1], sys.argv[2]
pat = re.compile(r'\[(\\-(\d+))\]')   # [\-1] [\-9] ...  (含转义反斜杠的负索引)
n_fixed = 0
with open(src, 'r', errors='replace') as fin, open(dst, 'w') as fout:
    for line in fin:
        if '\\-' in line and '[' in line:
            line, k = pat.subn(r'\[-\2\]', line)
            n_fixed += k
        fout.write(line)
print(f"fixed lines: {n_fixed}")
