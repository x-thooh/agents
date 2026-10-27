#!/usr/bin/env python3
"""evidence: 跑真实 Go 工具链，产 `impl.json` / `test.json`。

为什么必须有它：verify 是零依赖的**词法**门禁，只判「证据写了 pass」；build/vet/
test -race/覆盖率/benchmark/lint 的真假只有工具链知道。没有产证据的人时，`impl.json`
里的 `"build": "pass"` 只能靠手抄——那正是 `standards.md` 自己警告的假数据。

规矩：
  * 所有步骤 exit 0 才写文件；任何一步失败都不写，不产生半份证据；
  * 写出的证据带 `commit`（当前 HEAD）与 `at`（UTC 时间），scope 会校验 commit；
  * 本脚本不进 `make check`：`make check` 仍只读 JSON、不依赖 Go；
  * `config.json` 仍是 `example: true` 时拒绝运行——模板的示例数据不能被真证据覆盖。

用法: python3 .harness/scripts/evidence.py [--root DIR]
退出码: 0 = 已写入；1 = 工具链步骤失败；2 = 用法/环境/配置错误
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG_REL = ".harness/config.json"
IMPL_REL = ".harness/deliverables/artifacts/impl.json"
TEST_REL = ".harness/deliverables/artifacts/test.json"
BENCH = re.compile(r"^(Benchmark\S+)\s+\d+\s+([0-9.]+)\s+ns/op\b")


def run(cmd, cwd, env=None):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False, env=env)


def fail(message, output=""):
    print(f"evidence: {message}", file=sys.stderr)
    if output.strip():
        print(output.rstrip(), file=sys.stderr)
    return 1


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_head(root):
    proc = run(["git", "-C", str(root), "rev-parse", "HEAD"], root)
    return proc.stdout.strip() if proc.returncode == 0 else None


def changed(root, go_src):
    """返回 (改动 .go 文件数, 包目录列表)；干净工作树记 ["."]。"""
    proc = run(["git", "-C", str(root), "status", "--porcelain", "--", str(go_src)], root)
    if proc.returncode != 0:
        return 0, ["."]
    files = set()
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].split(" -> ")[-1].strip()
        if path.endswith(".go"):
            files.add(path)
    if not files:
        return 0, ["."]
    prefix = go_src.relative_to(root).as_posix()
    if prefix == ".":
        prefix = ""
    packages = set()
    for path in files:
        rel = path[len(prefix) + 1:] if prefix and path.startswith(prefix + "/") else path
        packages.add(os.path.dirname(rel) or ".")
    return len(files), sorted(packages)


def module_path(go_src):
    try:
        lines = (go_src / "go.mod").read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"读不了 {go_src}/go.mod: {exc}") from None
    for line in lines:
        if line.startswith("module "):
            return line.split(None, 1)[1].strip()
    raise ValueError(f"{go_src}/go.mod 缺 module 声明")


def parse_profile(profile, module, go_src):
    """按语句数统计覆盖率：{包目录: [总语句, 覆盖语句]}。"""
    stats = {}
    for line in profile.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("mode:"):
            continue
        parts = line.rsplit(None, 2)
        if len(parts) != 3:
            continue
        prefix, num, count = parts
        try:
            statements, hits = int(num), int(count)
        except ValueError:
            continue
        file_path = prefix.rsplit(":", 1)[0]
        if file_path.startswith(module + "/"):
            rel = file_path[len(module) + 1:]
        else:
            try:
                rel = Path(file_path).relative_to(go_src).as_posix()
            except ValueError:
                rel = file_path
        package = os.path.dirname(rel) or "."
        total, covered = stats.setdefault(package, [0, 0])
        stats[package] = [total + statements, covered + (statements if hits > 0 else 0)]
    return stats


def percentage(stats, packages):
    total = sum(stats[p][0] for p in packages if p in stats)
    covered = sum(stats[p][1] for p in packages if p in stats)
    if total == 0:
        raise ValueError("覆盖率样本为 0 条语句：检查 go_src / coverage.include 是否写对")
    return round(100.0 * covered / total, 1)


def coverage(config, profile, module, go_src):
    stats = parse_profile(profile, module, go_src)
    rules = config.get("coverage") or {}
    includes = [str(item).strip("/") for item in (rules.get("include") or []) if str(item).strip("/")]
    core_dirs = [str(item).strip("/") for item in (rules.get("core_packages") or []) if str(item).strip("/")]
    if not core_dirs:
        raise ValueError("config.coverage.core_packages 未配置：无法计算 core 覆盖率")

    def matches(package, prefixes):
        return any(package == p or package.startswith(p + "/") for p in prefixes)

    packages = [p for p in stats if not includes or matches(p, includes)]
    core = [p for p in packages if matches(p, core_dirs)]
    if not core:
        raise ValueError(f"core_packages {core_dirs} 没有命中任何包：检查包路径")
    return {"total": percentage(stats, packages), "core": percentage(stats, core)}


def parse_tests(output):
    """go test -json：只数顶层测试（不含 t.Run 子测试）。"""
    cases = 0
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        test = event.get("Test")
        if event.get("Action") == "pass" and test and "/" not in test:
            cases += 1
    return cases


def parse_bench(output):
    found = {}
    for line in output.splitlines():
        match = BENCH.match(line.strip())
        if not match:
            continue
        name = match.group(1)
        if name.rsplit("-", 1)[-1].isdigit():
            name = name.rsplit("-", 1)[0]
        found[name] = round(float(match.group(2)), 1)
    return found


def previous_baselines(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    for item in data.get("benchmarks") or []:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            value = item.get("baseline_ns_per_op")
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                out[item["name"]] = value
    return out


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="跑 Go 工具链并写 impl.json / test.json")
    parser.add_argument("--root", default=str(ROOT), help="仓库根目录（默认 = 本脚本向上两级）")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    try:
        config = json.loads((root / CONFIG_REL).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"evidence: 读不了 {CONFIG_REL}: {exc}", file=sys.stderr)
        return 2
    if config.get("example") is True:
        print("evidence: config.json 仍是示例（example: true）：先拷进目标仓库并去掉示例标记", file=sys.stderr)
        return 2

    go = os.environ.get("GO") or shutil.which("go")
    lint = os.environ.get("GOLANGCI_LINT") or shutil.which("golangci-lint")
    if not go:
        print("evidence: 需要 Go 工具链（GO=/path/to/go）", file=sys.stderr)
        return 2
    if not lint:
        print("evidence: 需要 golangci-lint（GOLANGCI_LINT=/path/to/golangci-lint）", file=sys.stderr)
        return 2

    go_src = root / str(config.get("go_src") or ".")
    if not go_src.is_dir():
        print(f"evidence: go_src 不存在: {go_src}", file=sys.stderr)
        return 2
    head = git_head(root)
    if head is None:
        print("evidence: 需要 git 仓库且有 HEAD：证据要绑定提交，否则无法判时效", file=sys.stderr)
        return 2

    # GO 是绝对路径时，把它所在目录放到 PATH 最前：golangci-lint 及其 formatter
    # 会再调用 `go`，不能让它落到另一个（可能坏掉的）shim 上。
    tool_env = os.environ.copy()
    if os.path.isabs(go):
        tool_env["PATH"] = str(Path(go).parent) + os.pathsep + tool_env.get("PATH", "")

    for label, cmd in (("go build", [go, "build", "./..."]), ("go vet", [go, "vet", "./..."])):
        proc = run(cmd, go_src, tool_env)
        if proc.returncode != 0:
            return fail(f"{label} 失败；未写入证据", proc.stdout + proc.stderr)

    cases = 0
    with tempfile.TemporaryDirectory(prefix="evidence-") as tmp:
        profile = Path(tmp) / "cover.out"
        proc = run(
            [go, "test", "-race", "-covermode=atomic", f"-coverprofile={profile}", "-json", "./..."],
            go_src,
            tool_env,
        )
        if proc.returncode != 0:
            return fail("go test -race 失败；未写入证据", proc.stdout + proc.stderr)
        cases = parse_tests(proc.stdout)
        try:
            cover = coverage(config, profile, module_path(go_src), go_src)
        except ValueError as exc:
            return fail(str(exc))

    proc = run([go, "test", "-run", "^$", "-bench", ".", "-benchmem", "./..."], go_src, tool_env)
    if proc.returncode != 0:
        return fail("benchmark 失败；未写入证据", proc.stdout + proc.stderr)
    current = parse_bench(proc.stdout)
    baseline = previous_baselines(root / TEST_REL)
    benchmarks = []
    for name, ns in sorted(current.items()):
        base = baseline.get(name)
        benchmarks.append({
            "name": name,
            "ns_per_op": ns,
            "baseline_ns_per_op": round(base if base is not None else ns, 1),
        })

    proc = run([lint, "run", "./..."], go_src, tool_env)
    if proc.returncode != 0:
        return fail("golangci-lint 失败；未写入证据", proc.stdout + proc.stderr)

    commit = head
    at = now_iso()
    changed_files, changed_packages = changed(root, go_src)
    write_json(root / IMPL_REL, {
        "build": "pass",
        "vet": "pass",
        "lint": "pass",
        "changed_packages": changed_packages,
        "changed_files": changed_files,
        "commit": commit,
        "at": at,
        "notes": f"由 .harness/scripts/evidence.py 在 {commit[:12]} 生成；build/vet/lint 全部 exit 0",
    })
    write_json(root / TEST_REL, {
        "cases": cases,
        "race": "pass",
        "coverage": cover,
        "benchmarks": benchmarks,
        "commit": commit,
        "at": at,
        "notes": "由 .harness/scripts/evidence.py 生成；覆盖率与 benchmark 来自真实命令",
    })
    print(f"evidence: 已写入 {IMPL_REL} / {TEST_REL}（case {cases}，覆盖率 {cover['total']}%）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
