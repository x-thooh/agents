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


def edit_json(root, rel, mutate):
    path = root / rel
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_text(root, rel, extra):
    path = root / rel
    path.write_text(path.read_text(encoding="utf-8") + extra, encoding="utf-8")


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


def reverse_case(name, scope, expected_code, mutate):
    with tempfile.TemporaryDirectory(prefix=f"go-{scope}-") as tmp:
        root = copy_root(tmp)
        mutate(root)
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
        "gates: reject blocks later stages",
        "gates",
        "GATE004",
        lambda root: edit_json(
            root,
            ".harness/deliverables/gates/03-impl.json",
            lambda data: data.update(
                {
                    "result": "reject",
                    "rework": [{"issue": "go vet 报错", "action": "修", "rerun_stages": ["impl"]}],
                }
            ),
        ),
    )
    reverse_case(
        "contract: interface without error codes",
        "contract",
        "CTR002",
        lambda root: edit_json(
            root,
            ".harness/deliverables/artifacts/contract.json",
            lambda data: data["interfaces"][0].update({"errors": []}),
        ),
    )
    reverse_case(
        "design: package dependency cycle",
        "design",
        "DES002",
        lambda root: edit_json(
            root,
            ".harness/deliverables/artifacts/design.json",
            lambda data: [
                pkg.update({"deps": ["internal/httpapi"]})
                for pkg in data["packages"]
                if pkg["name"] == "internal/order"
            ],
        ),
    )
    reverse_case(
        "layout: main.go too large",
        "layout",
        "LAY004",
        lambda root: append_text(
            root,
            "sample/cmd/ordersvc/main.go",
            "".join(f"\n// pad {i}" for i in range(100)) + "\n",
        ),
    )
    reverse_case(
        "runtime: panic in library code",
        "runtime",
        "RUNT001",
        lambda root: append_text(
            root,
            "sample/internal/order/order.go",
            "\nfunc boom() {\n\tpanic(\"boom\")\n}\n",
        ),
    )
    reverse_case(
        "impl: trailing whitespace",
        "impl",
        "IMP002",
        lambda root: append_text(root, "sample/internal/config/config.go", "// pad \n"),
    )
    reverse_case(
        "test: package without test file",
        "test",
        "TST001",
        lambda root: (root / "sample/internal/config/config_test.go").unlink(),
    )
    reverse_case(
        "review: author self-approves",
        "review",
        "REV002",
        lambda root: edit_json(
            root,
            ".harness/deliverables/artifacts/review.json",
            lambda data: data["mrs"][0].update({"approvals": ["dev-a", "dev-b", "dev-c"]}),
        ),
    )
    reverse_case(
        "release: smoke test not green",
        "release",
        "REL003",
        lambda root: edit_json(
            root,
            ".harness/deliverables/artifacts/release.json",
            lambda data: data["smoke"].update({"passed": 10}),
        ),
    )

    reverse_case(
        "state: task points at unknown stage",
        "gates",
        "GATE007",
        lambda root: edit_json(
            root,
            ".harness/tasks/board.json",
            lambda data: data["tasks"][0].update({"stage": "not-a-stage"}),
        ),
    )
    reverse_case(
        "state: codebase guide edited by hand",
        "gates",
        "GUIDE001",
        lambda root: edit_json(
            root,
            ".harness/codebase-guide/index.json",
            lambda data: data["entries"].pop(0),
        ),
    )

    print("ALL REVERSE TESTS PASSED")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
