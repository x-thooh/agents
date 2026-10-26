#!/usr/bin/env python3
"""Reverse tests: one deliberate defect per scope must yield its exact code.

Usage: python3 tests/reverse.py
Exit 0 only when the positive control and every reverse case pass.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def copy_root(tmp):
    target = Path(tmp) / "root"
    shutil.copytree(
        ROOT,
        target,
        ignore=shutil.ignore_patterns("__pycache__", ".ruff_cache", "tests"),
    )
    return target


def read_json(root, rel):
    return json.loads((root / rel).read_text(encoding="utf-8"))


def write_json(root, rel, data):
    (root / rel).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_verify(root, scope=None, fix=False):
    cmd = [
        sys.executable,
        str(root / ".harness/scripts/verify.py"),
        "--root",
        str(root),
        "--json",
    ]
    if scope:
        cmd.extend(["--scope", scope])
    if fix:
        cmd.append("--fix")
    # 不写字节码：否则 __pycache__ 会让临时仓库变脏，--fix 的前置检查会误拒
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, env=env)
    if not proc.stdout.strip() and proc.returncode == 2:
        # 前置条件不满足时 verify 只往 stderr 说话，没有 JSON——这是契约的一部分
        return {"findings": [], "summary": {"errors": 0, "warns": 0}, "stderr": proc.stderr}, 2
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print("verify output was not JSON", file=sys.stderr)
        print(proc.stdout, file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        raise
    return payload, proc.returncode


# --- --fix 相关 -------------------------------------------------------------

GUIDE_REL = ".harness/codebase-guide/index.json"
GATE_DELIVERABLE = ".harness/deliverables/artifacts/requirements.json"


def git_init(root):
    """临时仓库自带身份，不依赖全局 git 配置。"""
    ident = ["-c", "user.name=reverse", "-c", "user.email=reverse@example.invalid"]
    for step in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "base"]):
        subprocess.run(["git", *ident, *step], cwd=root, check=True, capture_output=True)


def mutate_guide(root):
    """把索引清空：GUIDE001 必报，且能被 --fix 复原成正确内容。"""
    data = read_json(root, GUIDE_REL)
    data["entries"] = []
    write_json(root, GUIDE_REL, data)


def guide_entries(root):
    return len(read_json(root, GUIDE_REL)["entries"])


def codes_of(payload):
    return [finding["code"] for finding in payload["findings"]]


def check_guide_regenerated():
    """--fix 之后 GUIDE001 必须消失，且索引真的被重新生成了（不是只把报错藏掉）。"""

    def check(root, payload):
        if "GUIDE001" in codes_of(payload):
            raise AssertionError(f"GUIDE001 仍在：{codes_of(payload)}")
        if guide_entries(root) == 0:
            raise AssertionError("索引没被重新生成（entries 仍为空）")

    return check


def check_still_broken(code, rel):
    """非派生类 ERROR 必须原样留着，且不许脚本替人补文件。"""

    def check(root, payload):
        if code not in codes_of(payload):
            raise AssertionError(f"期望 {code} 仍报，实际 {codes_of(payload)}")
        if (root / rel).exists():
            raise AssertionError(f"{rel} 被自动创建了：这不是派生数据，不该由脚本代劳")

    return check


def check_guide_matches_head():
    """前置条件不满足时一个字都不许改：索引必须还等于 HEAD 里的版本。"""

    def check(root, payload):
        proc = subprocess.run(
            ["git", "-C", str(root), "diff", "--quiet", "HEAD", "--", GUIDE_REL],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise AssertionError("索引被改动了：前置条件不满足时不该动手")

    return check


def check_guide_untouched():
    """非 git 场景下没法用 git 比对，改看内容：mutate_guide 把 entries 清空了。"""

    def check(root, payload):
        if guide_entries(root) != 0:
            raise AssertionError("索引被改动了：前置条件不满足时不该动手")

    return check


def fix_case(name, setup, expect_rc, check):
    with tempfile.TemporaryDirectory(prefix="dh-fix-") as tmp:
        root = copy_root(tmp)
        setup(root)
        payload, rc = run_verify(root, fix=True)
        if rc != expect_rc:
            raise AssertionError(
                f"{name}: 期望退出码 {expect_rc}，实际 {rc}；findings={codes_of(payload)}"
            )
        try:
            check(root, payload)
        except AssertionError as exc:
            raise AssertionError(f"{name}: {exc}") from None
        print(f"PASS {name}: exit {rc}")


def hooks_case(name, expect_code, strip_exec=False):
    """钩子执行位 / 存在性：丢了执行位时 git 静默跳过，只能靠断言发现。"""
    with tempfile.TemporaryDirectory(prefix="dh-hooks-") as tmp:
        root = copy_root(tmp)
        hook = root / ".harness/git-hooks/commit-msg"
        if strip_exec:
            hook.chmod(0o644)
        payload, rc = run_verify(root, "gates")
        codes = codes_of(payload)
        if rc == 0 or expect_code not in codes:
            raise AssertionError(f"{name}: 期望 {expect_code}，实际 rc={rc} codes={codes}")
        print(f"PASS {name}: {expect_code}")


def positive_control():
    payload, rc = run_verify(ROOT)
    errors = payload["summary"]["errors"]
    if errors != 0 or rc != 0:
        raise AssertionError(f"positive control failed: {errors} ERROR, exit {rc}")
    print(f"PASS positive control: 0 ERROR ({payload['summary']['warns']} example WARN)")


def reverse_case(name, rel, mutate, scope, expected_code):
    with tempfile.TemporaryDirectory(prefix=f"dh-{scope}-") as tmp:
        root = copy_root(tmp)
        data = read_json(root, rel)
        mutate(data)
        write_json(root, rel, data)
        payload, rc = run_verify(root, scope)
        findings = payload["findings"]
        codes = [finding["code"] for finding in findings]
        if payload["summary"]["errors"] < 1 or rc == 0:
            raise AssertionError(f"{name}: expected an ERROR, got {codes}")
        if expected_code not in codes:
            raise AssertionError(f"{name}: expected {expected_code}, got {codes}")
        if any(finding["scope"] != scope for finding in findings):
            raise AssertionError(f"{name}: findings leaked outside scope {scope}")
        print(f"PASS {name}: {expected_code}")


def main():
    positive_control()

    hooks_case("gates: commit-msg 丢了执行位（git 会静默跳过）", "GATE008", strip_exec=True)

    # conf：键名拼错必须报，不能静默忽略（静默忽略 = 整条扫描被关掉）
    reverse_case(
        "conf: 拼错的配置键不会被静默忽略",
        ".harness/config.json",
        lambda data: data.update({"task_max_daysx": 3}),
        "conf",
        "CONF001",
    )

    reverse_case(
        "gate order: reject blocks later stages",
        ".harness/deliverables/gates/03-dev.json",
        lambda data: data.update(
            {
                "result": "reject",
                "rework": [{"issue": "CI red", "action": "fix", "rerun_stages": ["dev"]}],
            }
        ),
        "gates",
        "GATE004",
    )
    reverse_case(
        "requirements: task estimate > 3 days",
        ".harness/deliverables/artifacts/requirements.json",
        lambda data: data["tasks"][0].update({"estimate_days": 5}),
        "requirements",
        "REQ003",
    )
    reverse_case(
        "design: contract unsigned",
        ".harness/deliverables/artifacts/design.json",
        lambda data: data["contract"].update({"signed_by": []}),
        "design",
        "DES004",
    )
    reverse_case(
        "dev: core coverage below threshold",
        ".harness/deliverables/artifacts/dev.json",
        lambda data: data["coverage"].update({"core": 10}),
        "dev",
        "DEV002",
    )
    reverse_case(
        "integration: interface failed",
        ".harness/deliverables/artifacts/integration.json",
        lambda data: data["interfaces"][0].update({"status": "fail"}),
        "integration",
        "INT001",
    )
    reverse_case(
        "selftest: P1 left open",
        ".harness/deliverables/artifacts/selftest.json",
        lambda data: data["defects"].update({"P1": 1}),
        "selftest",
        "ST001",
    )
    reverse_case(
        "review: MR too large without approval",
        ".harness/deliverables/artifacts/review.json",
        lambda data: data["mrs"][0].update({"lines_changed": 900}),
        "review",
        "REV001",
    )
    reverse_case(
        "coherence: requirement missing from traceability",
        ".harness/deliverables/artifacts/coherence.json",
        lambda data: data["traceability"].pop(0),
        "coherence",
        "COH002",
    )
    reverse_case(
        "submission: smoke test failed",
        ".harness/deliverables/artifacts/submission.json",
        lambda data: data["smoke"].update({"passed": 19}),
        "submission",
        "SUB002",
    )

    reverse_case(
        "state: task points at unknown stage",
        ".harness/tasks/board.json",
        lambda data: data["tasks"][0].update({"stage": "not-a-stage"}),
        "gates",
        "GATE007",
    )
    reverse_case(
        "state: codebase guide edited by hand",
        ".harness/codebase-guide/index.json",
        lambda data: data["entries"].pop(0),
        "gates",
        "GUIDE001",
    )

    # --- --fix：只修派生数据；不越界、不猜、没有回滚点就不动手 ---

    fix_case(
        "fix: 派生数据自动修好（GUIDE001，目标文件脏也能修）",
        lambda root: (git_init(root), mutate_guide(root)),
        0,
        check_guide_regenerated(),
    )
    fix_case(
        "fix: 不越界（GATE006 不代劳补文件）",
        lambda root: ((root / GATE_DELIVERABLE).unlink(), git_init(root)),
        1,
        check_still_broken("GATE006", GATE_DELIVERABLE),
    )
    fix_case(
        "fix: 无关文件脏时拒绝动手",
        lambda root: (
            git_init(root),
            (root / "scratch.txt").write_text("wip\n", encoding="utf-8"),
        ),
        2,
        check_guide_matches_head(),
    )
    fix_case(
        "fix: 非 git 仓库拒绝动手",
        mutate_guide,
        2,
        check_guide_untouched(),
    )

    print("ALL REVERSE TESTS PASSED")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
