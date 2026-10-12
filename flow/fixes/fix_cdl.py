#!/usr/bin/env python3
"""修复 OpenROAD write_cdl 输出的缺尾单元名（LVS 前置修复）。

## 现象
LVS 比对时网表读不进去 / 器件数对不上。检查 APR 输出的 CDL，发现部分 `X` 开头
的实例行缺少末尾的单元名：

    X4689_ A(net678) B(net12) Y(net33)          ← 没有 sky130_fd_sc_hd__nor2_4

CDL 的实例行格式是 `X<inst> <pin>(<net>)... <cellname>`，少了单元名，LVS 工具就无法
判定这是哪种器件。

## 做法
从 APR 的 `6_final.v` 反查「实例 → 单元类型」映射，给缺名的 `X` 行补上。

## 用法
    python3 fix_cdl.py --check <cdl> <6_final.v>     # 只数有多少行缺单元名，不改文件
    python3 fix_cdl.py         <cdl> <6_final.v>    # 就地修复（原文件被覆盖）

## 注意
默认就地覆盖。想留底稿先自己 `cp` 一份；CDL 通常只有几 MB，复制成本可忽略。
"""

import re
import sys


def build_map(v_path):
    """从 APR 网表建立 实例名 → 单元类型 的映射。"""
    inst2cell = {}
    vsrc = open(v_path, errors='replace').read()

    # 形如：  sky130_fd_sc_hd__nor2_4 _4689_ (.A(net678),
    for m in re.finditer(r'(sky130_fd_sc_hd__\w+)\s+([\w.\\]+)\s*\(', vsrc):
        inst = m.group(2).strip('\\')
        inst2cell[inst] = m.group(1)

    # 兜底：泛化的 <cell> <inst> ( 形式
    for m in re.finditer(r'(\w+)\s+(_\d+_|\w+_leaf_\d+_\w+)\s*\(', vsrc):
        inst2cell.setdefault(m.group(2), m.group(1))

    return inst2cell


def fix(cdl_path, v_path, check_only=False):
    """返回 (缺名的行数, 成功补上的行数, 修好的行列表或 None)。"""
    inst2cell = build_map(v_path)

    missing = 0
    fixed = 0
    out = []
    for ln in open(cdl_path, errors='replace'):
        m = re.match(r'^(X\S+)\s+(.*)$', ln.strip())
        if m and not re.search(r'sky130_fd_sc_hd__\w+\s*$', m.group(2)):
            missing += 1
            inst = m.group(1)
            cell = inst2cell.get(inst) or inst2cell.get(inst[1:])
            if cell:
                fixed += 1
                if not check_only:
                    out.append("%s %s %s\n" % (m.group(1), m.group(2), cell))
                continue
        if not check_only:
            out.append(ln if ln.endswith('\n') else ln + '\n')

    if check_only:
        return missing, fixed, None
    return missing, fixed, out


def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0 if argv else 2
    check_only = argv[0] == '--check'
    args = argv[1:] if check_only else argv
    if len(args) != 2:
        print("用法: fix_cdl.py [--check] <cdl> <6_final.v>", file=sys.stderr)
        return 2

    cdl_path, v_path = args
    missing, fixed, out = fix(cdl_path, v_path, check_only)

    if check_only:
        verdict = "需要修复" if missing else "无需修复"
        print("缺单元名 %d 行，其中 %d 行能从网表反查到单元 —— %s" % (missing, fixed, verdict))
        if missing and fixed < missing:
            print("有 %d 行反查不到单元，检查网表是否与 CDL 同源。" % (missing - fixed))
        return 0 if missing == 0 else 1

    if out is not None:
        open(cdl_path, 'w').writelines(out)
    print("fixed %d lines in %s" % (fixed, cdl_path))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
