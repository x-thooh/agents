#!/usr/bin/env python3
"""Reverse tests: one deliberate defect per scope must yield its exact code.

Usage: python3 tests/reverse.py
Exit 0 only when the positive control and every reverse case pass.
"""
import json
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


def run_verify(root, scope=None):
    cmd = [
        sys.executable,
        str(root / ".harness/scripts/verify.py"),
        "--root",
        str(root),
        "--json",
    ]
    if scope:
        cmd.extend(["--scope", scope])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print("verify output was not JSON", file=sys.stderr)
        print(proc.stdout, file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        raise
    return payload, proc.returncode


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

    print("ALL REVERSE TESTS PASSED")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
