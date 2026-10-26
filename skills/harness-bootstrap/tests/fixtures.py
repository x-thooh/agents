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
# 期望表住在 cases.py：改期望不该动引擎，改闸不该动数据（拆开前本文件 238 行，
# 越过了自己定的 200 行上限——而当时的 BUDGET001 只扫 scripts/，所以没人发现）。
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cases import CASES  # noqa: E402
from coverage import check_coverage  # noqa: E402


def run_case(fixture, extra):
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "audit.py"),
        "--skill-dir",
        str(FIXTURES / fixture),
        "--json",
        *extra,
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if not proc.stdout.strip():
        raise RuntimeError(f"audit 没输出 JSON（fixture={fixture}）：{proc.stderr.strip()}")
    return json.loads(proc.stdout)


def check_cli():
    """入口契约：`--only` 里拼错 scope 必须退出码 2——静默少跑一条检查是最坏的绿灯。"""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "audit.py"), "--only", "no-such-scope"],
        check=False, capture_output=True, text=True,
    )
    if proc.returncode != 2:
        return [f"--only 未知 scope 应退出 2，实际 {proc.returncode}"]
    if "Traceback" in proc.stderr:
        return ["--only 未知 scope 不应 traceback：那是崩溃，不是用法错误"]
    if "可选" not in proc.stderr:
        return ["--only 未知 scope 应列出可选项，实际：" + proc.stderr.strip()[:120]]
    return []


def main():
    failures = list(check_coverage()) + check_cli()
    for fixture, expected, extra in CASES:
        label = fixture + (" " + " ".join(extra) if extra else "")
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
