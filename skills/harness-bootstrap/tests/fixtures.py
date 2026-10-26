#!/usr/bin/env python3
"""把 tests/fixtures/ 的期望变成可执行的断言。

每个 fixture 一件缺陷，期望的 code 要**精确对上**——不是「有 ERROR 就算过」。
README 里那张手动命令表靠人记得跑；这张表把它变成 make check 的一部分。
不这么做的后果，SKILL.md §六 写过：scope 可能上线起就没执行过，跑一百次都「通过」。

正对照（ok-minimal）排第一：没有它，「全部符合期望」可能只是检查器根本没跑。

用法: python3 tests/fixtures.py
退出码: 0 = 全部符合期望；1 = 有偏差；2 = 环境错误
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"

# (fixture, 期望的 code 集合, 额外命令行参数)
CASES = (
    # 正对照：0 条发现。它一红，下面所有「符合期望」都不作数。
    ("ok-minimal", set(), ()),
    # 每个 scope 至少一条
    ("bad-frontmatter", {"FM004"}, ()),
    ("bad-bash-block", {"BASH001"}, ()),
    ("bad-description", {"FM008"}, ()),
    ("bad-description-trigger", {"FM009"}, ()),
    ("bad-baseline-rule", {"BASE001"}, ()),
    ("bad-zero-baseline", {"BASE003"}, ()),
    ("bad-expiry-decor", {"BASE004"}, ()),
    ("bad-host-loading", {"HOST001"}, ()),
    ("bad-dual-ledger", {"DUAL001"}, ()),
    ("bad-scope-grading", {"SCOPE001"}, ()),
    ("bad-version-ungated", {"VER001"}, ()),
    ("bad-xref", {"XREF001"}, ()),
    ("bad-xref-table", {"XREF002"}, ()),
    ("bad-relative-link", {"LINK004"}, ()),
    ("bad-xref-ext", {"XREFDOC002"}, ()),
    # 标准目录形状（本轮新增）
    ("bad-struct-extra", {"STRUCT001"}, ()),
    ("bad-struct-singular", {"STRUCT001"}, ()),
    ("bad-struct-refs-content", {"STRUCT002"}, ()),
    # 调度器体征：换一个「长成实现」的调度器去审合规样本
    ("ok-minimal", {"LAYOUT001"}, ("--dispatch", "tests/fixtures/bad-inline-scope/scripts/audit.py")),
)


def run_case(fixture, extra):
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "audit.py"),
        "--skill-dir",
        str(FIXTURES / fixture),
        "--json",
        *extra,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not proc.stdout.strip():
        raise RuntimeError(f"audit 没输出 JSON（fixture={fixture}）：{proc.stderr.strip()}")
    return json.loads(proc.stdout)


def main():
    failures = []
    for fixture, expected, extra in CASES:
        label = fixture + (" +--dispatch" if extra else "")
        try:
            payload = run_case(fixture, extra)
        except RuntimeError as exc:
            failures.append(f"{label}: {exc}")
            continue
        findings = payload["findings"]
        actual = {f["code"] for f in findings}
        summary = payload["summary"]
        if actual != expected:
            failures.append(
                f"{label}: 期望 {sorted(expected) or '无'}，实际 {sorted(actual) or '无'}")
            continue
        if not expected and (summary["errors"] or summary["warns"]):
            failures.append(
                f"{label}: 正对照必须 0 ERROR 0 WARN，实际 "
                f"{summary['errors']} ERROR / {summary['warns']} WARN")
            continue
        print(f"PASS {label}: {sorted(expected) or '0 条发现'}")

    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
        print(f"{len(failures)} 例不符合期望", file=sys.stderr)
        return 1
    print(f"ALL {len(CASES)} FIXTURES MATCHED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
