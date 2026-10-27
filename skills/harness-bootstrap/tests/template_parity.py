#!/usr/bin/env python3
"""两套模板的共同文件必须逐字节一致——它们是副本，不是两套答案。

为什么需要：`baseline.py`、`check_commit.py`、`gen_guide.py`、钩子与
`workflow/contract.json` 在两套模板里是同一份实现。修一个基线 bug 要改两处，
而没有任何断言要求两边一致；只改一边时，两套模板的语义就静默分叉了。

只比较**确实应相同**的共同子集；`common.py` / `gates.py` / `registry.py` 因模板差异
而合法不同，不在表里。新增共同文件时把它加进 SHARED。

`verify.py` 曾经也在豁免名单里，理由是「因模板差异而合法不同」——实测它 195 行里 178 行
相同，差异只有 import 清单、SCOPES 与一句 `--help` 描述。整个文件因局部差异被全量豁免，
重复的主体就没人守了。治法不是把差异抹平，是把差异搬出去：scope 清单进 `registry.py`
（各域本来就该不同），调度骨架留在 `verify.py` 并纳入 SHARED。豁免的理由要能被复核——
「合法不同」四个字掩盖的是「哪里不同、有多少」。

用法: python3 tests/template_parity.py
退出码: 0 = 一致；1 = 分叉或缺失；2 = 环境错误
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "templates/delivery-harness"
GODEV = ROOT / "templates/go-dev-harness"

SHARED = (
    ".harness/scripts/verify.py",
    ".harness/scripts/wt.py",
    ".harness/scripts/scopes/baseline.py",
    ".harness/scripts/scopes/worktree.py",
    ".harness/scripts/check_commit.py",
    ".harness/scripts/evidence_age.py",
    ".harness/scripts/gen_guide.py",
    ".harness/scripts/retro.py",
    ".harness/scripts/retro_board.py",
    ".harness/scripts/retro_check.py",
    ".harness/scripts/round.py",
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
