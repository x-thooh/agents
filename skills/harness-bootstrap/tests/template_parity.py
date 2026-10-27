#!/usr/bin/env python3
"""两套模板的共同文件必须逐字节一致——它们是副本，不是两套答案。

为什么需要：`baseline.py`、`check_commit.py`、`gen_guide.py`、钩子与
`workflow/contract.json` 在两套模板里是同一份实现。修一个基线 bug 要改两处，
而没有任何断言要求两边一致；只改一边时，两套模板的语义就静默分叉了。

只比较**确实应相同**的共同子集；`common.py` / `gates.py` / `verify.py` 因模板差异
而合法不同，不在表里。新增共同文件时把它加进 SHARED。

用法: python3 tests/template_parity.py
退出码: 0 = 一致；1 = 分叉或缺失；2 = 环境错误
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "templates/delivery-harness"
GODEV = ROOT / "templates/go-dev-harness"

SHARED = (
    ".harness/scripts/scopes/baseline.py",
    ".harness/scripts/check_commit.py",
    ".harness/scripts/gen_guide.py",
    ".harness/git-hooks/pre-commit",
    ".harness/git-hooks/commit-msg",
    ".harness/workflow/contract.json",
    ".harness/workflow/transitions.json",
    ".harness/accepted.json",
    ".harness/baseline.txt",
    ".harness/deliverables/ledgers/changes.json",
    ".harness/deliverables/ledgers/exceptions.json",
    "tests/commit_msg.py",
)


def main():
    bad = []
    for rel in SHARED:
        left, right = DELIVERY / rel, GODEV / rel
        if not left.is_file() or not right.is_file():
            bad.append(f"缺文件: {rel}（delivery={left.is_file()}, go-dev={right.is_file()}）")
        elif left.read_bytes() != right.read_bytes():
            bad.append(f"内容分叉: {rel}")
    if bad:
        for line in bad:
            print(f"FAIL {line}", file=sys.stderr)
        print(f"{len(bad)} 个共同文件不一致：修两边，或把合法差异从 SHARED 移走", file=sys.stderr)
        return 1
    print(f"PASS 模板共同文件 {len(SHARED)} 个逐字节一致")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except OSError as exc:
        print(f"环境错误: {exc}", file=sys.stderr)
        sys.exit(2)
