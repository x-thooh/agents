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


def edit_json(root, rel, mutate):
    path = root / rel
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_text(root, rel, extra):
    path = root / rel
    path.write_text(path.read_text(encoding="utf-8") + extra, encoding="utf-8")


def replace_text(root, rel, old, new):
    path = root / rel
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise AssertionError(f"{rel} 里找不到待替换片段：{old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


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
GATE_DELIVERABLE = ".harness/deliverables/artifacts/contract.json"


def git_init(root):
    """临时仓库自带身份，不依赖全局 git 配置。"""
    ident = ["-c", "user.name=reverse", "-c", "user.email=reverse@example.invalid"]
    for step in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "base"]):
        subprocess.run(["git", *ident, *step], cwd=root, check=True, capture_output=True)


def mutate_guide(root):
    """把索引清空：GUIDE001 必报，且能被 --fix 复原成正确内容。"""
    edit_json(root, GUIDE_REL, lambda data: data.update({"entries": []}))


def guide_entries(root):
    return len(json.loads((root / GUIDE_REL).read_text(encoding="utf-8"))["entries"])


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
    with tempfile.TemporaryDirectory(prefix="go-fix-") as tmp:
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


def positive_control():
    payload, rc = run_verify(ROOT)
    errors = payload["summary"]["errors"]
    if errors != 0 or rc != 0:
        raise AssertionError(f"positive control failed: {errors} ERROR, exit {rc}")
    print(f"PASS positive control: 0 ERROR ({payload['summary']['warns']} example WARN)")


def reverse_case(name, scope, expected_code, mutate, resync_guide=True):
    with tempfile.TemporaryDirectory(prefix=f"go-{scope}-") as tmp:
        root = copy_root(tmp)
        mutate(root)
        if resync_guide:
            # 改文件会让 codebase-guide 索引漂移，那等于给样本加了第二个缺陷。
            # 样本必须只有一个缺陷，所以改完先把派生数据同步回去。
            subprocess.run(
                [sys.executable, str(root / ".harness/scripts/gen_guide.py"), str(root)],
                check=True, capture_output=True,
            )
        payload, rc = run_verify(root, scope)
        findings = payload["findings"]
        errors = {finding["code"] for finding in findings if finding["severity"] == "ERROR"}
        if not errors or rc == 0:
            raise AssertionError(f"{name}: expected an ERROR, got {sorted(errors)}")
        if expected_code not in errors:
            raise AssertionError(f"{name}: expected {expected_code}, got {sorted(errors)}")
        # 一件缺陷只该产出一个 ERROR：多出来的说明样本被污染了，判据随之失效
        if errors != {expected_code}:
            raise AssertionError(f"{name}: 期望唯一的 ERROR 是 {expected_code}，实际 {sorted(errors)}")
        if any(finding["scope"] != scope for finding in findings):
            raise AssertionError(f"{name}: findings leaked outside scope {scope}")
        print(f"PASS {name}: {expected_code}")


def warn_case(name, scope, expected_code, mutate):
    """WARN 级断言的反向测试：期望 0 ERROR，且该 code 以 WARN 出现。"""
    with tempfile.TemporaryDirectory(prefix=f"go-{scope}-warn-") as tmp:
        root = copy_root(tmp)
        mutate(root)
        subprocess.run(
            [sys.executable, str(root / ".harness/scripts/gen_guide.py"), str(root)],
            check=True, capture_output=True,
        )
        payload, rc = run_verify(root, scope)
        findings = payload["findings"]
        warns = {finding["code"] for finding in findings if finding["severity"] == "WARN"}
        if rc != 0 or payload["summary"]["errors"] != 0:
            raise AssertionError(f"{name}: 期望 0 ERROR，实际 {payload['summary']['errors']}")
        if warns != {expected_code}:
            raise AssertionError(f"{name}: 期望唯一的 WARN 是 {expected_code}，实际 {sorted(warns)}")
        print(f"PASS {name}: {expected_code} (WARN)")


def main():
    positive_control()

    # conf：键名拼错必须报，不能静默忽略（静默忽略 = 整条扫描被关掉）
    reverse_case(
        "conf: 拼错的配置键不会被静默忽略",
        "conf",
        "CONF001",
        lambda root: edit_json(
            root, ".harness/config.json", lambda data: data.update({"go_srcx": "typo"})
        ),
    )

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
        "gates: lefthook 多声明一个没有实现的 hook",
        "gates",
        "GATE008",
        lambda root: append_text(
            root,
            "lefthook.yml",
            "\npre-push:\n  jobs:\n    - name: x\n      run: sh .harness/git-hooks/pre-push\n",
        ),
    )
    reverse_case(
        "gates: 钩子没有执行位（git 会静默跳过）",
        "gates",
        "GATE008",
        lambda root: os.chmod(root / ".harness/git-hooks/commit-msg", 0o644),
    )
    reverse_case(
        "gates: lefthook 内联检查（第二份定义）",
        "gates",
        "GATE008",
        lambda root: replace_text(
            root,
            "lefthook.yml",
            "run: sh .harness/git-hooks/pre-commit",
            "run: go vet ./...",
        ),
    )
    reverse_case(
        "gates: 规范表引用不存在的断言代码",
        "gates",
        "GATE009",
        lambda root: append_text(
            root,
            ".harness/specs/standards.md",
            "\n| 假规范 | 假的 | `TST999` | 本项目 |\n",
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
        resync_guide=False,   # 这一例测的就是索引被改坏，不能同步
    )

    # --- 风格类断言（来源：CodeReviewComments / Uber Go Style Guide / project-layout）---

    reverse_case(
        "layout: receiver named this",
        "layout",
        "LAY008",
        lambda root: append_text(root, "sample/internal/order/order.go",
                                 "\nfunc (this *Order) touch() {}\n"),
    )
    reverse_case(
        "layout: mixed receiver types",
        "layout",
        "LAY009",
        lambda root: append_text(
            root, "sample/internal/order/order.go",
            "\nfunc (o *Order) paid() bool { return o.Status == StatusPaid }\n"
            "func (o Order) amount() int64 { return o.Amount }\n"),
    )
    reverse_case(
        "layout: package comment detached by blank line",
        "layout",
        "LAY010",
        lambda root: replace_text(
            root, "sample/internal/order/order.go",
            "// Package order implements order creation and lookup.\npackage order",
            "// Package order implements order creation and lookup.\n\npackage order"),
    )
    reverse_case(
        "layout: src directory",
        "layout",
        "LAY011",
        lambda root: (root / "sample/src").mkdir(),
    )
    warn_case(
        "layout: doc comment without closing period",
        "layout",
        "LAY012",
        lambda root: append_text(root, "sample/internal/order/order.go",
                                 "\n// Note is a note without a closing period\nfunc Note() {}\n"),
    )
    reverse_case(
        "runtime: error string capitalized",
        "runtime",
        "RUNT008",
        lambda root: append_text(root, "sample/internal/order/order.go",
                                 '\nfunc bad() error { return fmt.Errorf("Bad thing") }\n'),
    )
    reverse_case(
        "runtime: error variable without Err prefix",
        "runtime",
        "RUNT009",
        lambda root: append_text(root, "sample/internal/order/order.go",
                                 '\nvar NotFound = errors.New("not found")\n'),
    )
    reverse_case(
        "runtime: init() in library code",
        "runtime",
        "RUNT010",
        lambda root: append_text(root, "sample/internal/config/config.go", "\nfunc init() {}\n"),
    )
    reverse_case(
        "impl: stdlib and third-party in one import group",
        "impl",
        "IMP005",
        lambda root: replace_text(
            root, "sample/internal/config/config.go",
            '\t"time"\n)',
            '\t"time"\n\t"example.com/ordersvc/internal/order"\n)'),
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
