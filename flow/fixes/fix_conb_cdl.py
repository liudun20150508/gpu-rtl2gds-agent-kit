#!/usr/bin/env python3
"""把 conb tie cell 改写成直连，让原理图 CDL 与版图提取结果对得上。

## 现象
LVS 在 conb（tie high / tie low）单元上对不上：原理图 CDL 里保留了
`sky130_fd_sc_hd__conb_1` 实例，而版图提取出的网表里 tie 金属直接把
LO 短到 VGND、HI 短到 VPWR，那个单元在提取网表里根本不存在。

## 做法
按版图的实际连接重写原理图 CDL：
  * 删掉所有 conb 实例行；
  * 把它们的 HI 连到的网络全量改名为 VPWR、LO 连到的网络改名为 VGND；
  * 删掉不再被引用的 conb SUBCKT 定义。

改名用词边界匹配（`(?<![A-Za-z0-9_\\[\\]])...(?![A-Za-z0-9_\\[\\]])`），
避免 `HI_2` 被 `HI` 的替换误伤。

## 用法
    python3 fix_conb_cdl.py --check <cdl>    # 只数有多少个 conb tie，不改文件
    python3 fix_conb_cdl.py         <cdl>    # 就地改写（原文件被覆盖）

## 注意
默认就地覆盖。这是 LVS-only 的修复，别拿改过的 CDL 去做别的用途。
"""

import re
import sys

# SUBCKT conb 的引脚顺序：VGND VNB VPB VPWR HI LO
PAT = re.compile(
    r'^X(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+sky130_fd_sc_hd__conb_[12]\s*$')


def rewrite(path, check_only=False):
    """返回 (conb 实例数, 改名条数, 新内容或 None)。"""
    src = open(path, errors='replace').read()

    renames = []   # (old, new)
    out = []
    removed = 0
    for ln in src.split('\n'):
        m = PAT.match(ln.strip())
        if m:
            vgnd, _vnb, _vpb, vpwr, hi, lo = (m.group(2), m.group(3), m.group(4),
                                              m.group(5), m.group(6), m.group(7))
            renames.append((hi, vpwr))
            renames.append((lo, vgnd))
            removed += 1
            continue
        out.append(ln)

    if check_only:
        return removed, len(renames), None

    txt = '\n'.join(out)
    for old, new in renames:
        if old == new:
            continue
        txt = re.sub(r'(?<![A-Za-z0-9_\[\]])' + re.escape(old) + r'(?![A-Za-z0-9_\[\]])',
                     new, txt)
    # 删掉不再被引用的 conb SUBCKT 定义
    txt = re.sub(r'\.SUBCKT sky130_fd_sc_hd__conb_[12].*?\.ENDS[^\n]*\n', '', txt,
                 flags=re.S)
    return removed, len(renames), txt


def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0 if argv else 2
    check_only = argv[0] == '--check'
    args = argv[1:] if check_only else argv
    if len(args) != 1:
        print("用法: fix_conb_cdl.py [--check] <cdl>", file=sys.stderr)
        return 2

    path = args[0]
    removed, nrenames, txt = rewrite(path, check_only)

    if check_only:
        verdict = "需要改写" if removed else "无需改写"
        print("conb tie 实例 %d 个（%d 条网络改名）—— %s" % (removed, nrenames, verdict))
        return 0 if removed == 0 else 1

    open(path, 'w').write(txt)
    print("rewrote %d conb ties in %s" % (removed, path))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
