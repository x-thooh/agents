"""test: 测试证据（覆盖率 / race / benchmark + commit 时效）+ 每包必须有测试 + 测试卫生。"""
import re
from pathlib import Path

from .common import (
    add,
    as_dict,
    as_list,
    check_evidence_commit,
    check_fields,
    go_files,
    go_package,
    go_src,
    load_json,
    number,
    quality_get,
    rel_to,
    warn_example,
)

NAME = "test"
REL = ".harness/deliverables/artifacts/test.json"
SKIP = re.compile(r"\bt\.Skip(f|Now)?\(")
SLEEP = re.compile(r"\btime\.Sleep\(")


def run(ctx, findings):
    root = Path(ctx["root"])
    quality = as_dict(ctx.get("quality"))
    data = load_json(root, REL, NAME, findings, "TST002")
    if isinstance(data, dict):
        warn_example(data, REL, NAME, findings, ctx["strict"])
        ok = check_fields(data, ("coverage", "race", "cases", "commit", "at"), NAME, REL, findings, "TST002")
        if ok:
            check_evidence_commit(root, data, REL, NAME, "TST007", findings)
        check_coverage(data, quality, findings)
        check_race(data, findings)
        check_benchmarks(data, findings)
    check_packages(root, quality, findings)
    check_hygiene(root, quality, findings)


def check_coverage(data, quality, findings):
    coverage = as_dict(data.get("coverage"))
    for key, threshold_key in (("total", "total_min"), ("core", "core_min")):
        value = number(coverage.get(key))
        minimum = quality_get(quality, f"coverage.{threshold_key}", 0)
        if value is None:
            add(findings, "ERROR", NAME, REL, 1, "TST002", f"coverage.{key} 必须是数字")
            continue
        if value < minimum:
            add(findings, "ERROR", NAME, REL, 1, "TST002",
                f"coverage.{key} = {value}，低于阈值 {minimum}")


def check_race(data, findings):
    if data.get("race") != "pass":
        add(findings, "ERROR", NAME, REL, 1, "TST004",
            f"race = {data.get('race')!r}，必须为 'pass'（go test -race 无数据竞争）")


def check_benchmarks(data, findings):
    for bench in as_list(data.get("benchmarks")):
        if not isinstance(bench, dict):
            add(findings, "ERROR", NAME, REL, 1, "TST003", "benchmarks 条目必须是对象")
            continue
        current = number(bench.get("ns_per_op"))
        baseline = number(bench.get("baseline_ns_per_op"))
        if current is None or baseline is None or baseline <= 0:
            add(findings, "ERROR", NAME, REL, 1, "TST003",
                f"benchmark {bench.get('name', '?')} 缺 ns_per_op / baseline_ns_per_op")
            continue
        if current > baseline * 1.2:
            add(findings, "ERROR", NAME, REL, 1, "TST003",
                f"benchmark {bench.get('name', '?')} 从 {baseline}ns 退化到 {current}ns（>20%）")


def check_packages(root, quality, findings):
    src = go_src(root, quality)
    dirs = {}
    for path in go_files(src, include_tests=False):
        if go_package(path) == "main":
            continue
        dirs.setdefault(path.parent, []).append(path)
    for directory in sorted(dirs):
        has_test = any(p.name.endswith("_test.go") for p in directory.glob("*.go"))
        if not has_test:
            add(findings, "ERROR", NAME, rel_to(root, directory), 1, "TST001",
                "包内没有 _test.go：导出行为必须有测试")


def check_hygiene(root, quality, findings):
    src = go_src(root, quality)
    for path in go_files(src):
        if not path.name.endswith("_test.go"):
            continue
        rel = rel_to(root, path)
        for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if SKIP.search(line) and "//" not in line:
                add(findings, "WARN", NAME, rel, idx, "TST005",
                    "t.Skip 必须同行写明跳过理由")
            if SLEEP.search(line):
                add(findings, "WARN", NAME, rel, idx, "TST006",
                    "测试里 time.Sleep 会拖慢且不稳定：用 channel/Eventually")
