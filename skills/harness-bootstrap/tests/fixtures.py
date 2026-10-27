#!/usr/bin/env python3
"""把 tests/fixtures/ 的期望变成可执行的断言。

每个 fixture 一件缺陷，期望的 code 要**精确对上**——不是「有 ERROR 就算过」。
README 里那张手动命令表靠人记得跑；这张表把它变成 make check 的一部分。
不这么做的后果，SKILL.md §六 写过：scope 可能上线起就没执行过，跑一百次都「通过」。

**「精确对上」包括条数，不只是 code 集合**：只比集合时，一条规则在同一个 fixture 上
多报一次也照样绿。实测代价——`bad-template-phantom-path` 声称守「能解析的路径必须放过」，
把 `tplpath` 的存在性检查摘掉（退化成「见到反引号就报」），它报出 2 条 TP001 而期望集合
仍是 `{TP001}`，**PASS**。集合相等是「这条规则响过」，条数相等才是「它只在该响的地方响」。
所以这里同时判 `len(findings) == len(expected)`：一个 fixture 一件缺陷，就该恰好一条发现。

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
        # 条数与集合一起判：一个 fixture 一件缺陷，多报一条也是漂移（误报方向）。
        if actual != expected or len(findings) != len(expected):
            failures.append(
                f"{label}: 期望 {sorted(expected) or '无'} 各一条，实际 {len(findings)} 条 "
                f"{sorted(actual) or '无'}")
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
