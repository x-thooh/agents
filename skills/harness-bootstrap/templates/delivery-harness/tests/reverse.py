#!/usr/bin/env python3
"""Reverse tests: one deliberate defect per scope must yield its exact code.

Usage: python3 tests/reverse.py
Exit 0 only when the positive control and every reverse case pass.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COVERED = set()


def registered_scopes():
    """verify.py 的注册表——新增 scope 却没反向用例时，这里会红。"""
    text = (ROOT / ".harness/scripts/registry.py").read_text(encoding="utf-8")
    match = re.search(r"SCOPES\s*=\s*\((.*?)\)", text, re.S)
    if not match:
        raise AssertionError("registry.py 里找不到 SCOPES 注册表")
    return set(re.findall(r"\b([a-z][a-z0-9_]*)\b", match.group(1)))


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



ARTIFACT_AGE_REL = ".harness/deliverables/artifacts/requirements.json"


def evidence_age_case():
    """证据时效：commit 与 HEAD 不一致即 ERROR。

    没有 git 时 verify 只 WARN（判不了就说判不了），所以这个用例先 git_init——
    否则它测到的是「没有 git」那条分支，而不是「证据过期」这一条。
    """
    COVERED.add("gates")
    with tempfile.TemporaryDirectory(prefix="dh-age-") as tmp:
        root = copy_root(tmp)
        git_init(root)
        data = read_json(root, ARTIFACT_AGE_REL)
        data.pop("example", None)
        data["at"] = "2026-01-01T00:00:00Z"
        data["commit"] = "0" * 40
        write_json(root, ARTIFACT_AGE_REL, data)
        payload, rc = run_verify(root, "gates")
        codes = {f["code"] for f in payload["findings"] if f["severity"] == "ERROR"}
        if rc != 1 or "GATE009" not in codes:
            raise AssertionError(f"证据时效: 期望 GATE009 ERROR，实际 {sorted(codes)}，rc={rc}")
        print("PASS 证据时效: commit 与 HEAD 不一致 → GATE009")


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
    COVERED.add(scope)
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


# --- baseline 账本 ---------------------------------------------------------

LEDGER_REL = ".harness/baseline.txt"
ACCEPTED_REL = ".harness/accepted.json"


def write_text(root, rel, body):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def replace_text(root, rel, old, new):
    path = root / rel
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise AssertionError(f"{rel} 里找不到待替换片段：{old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def text_reverse_case(name, rel, mutate, scope, expected_code):
    """非 JSON 文件（AGENTS.md）的反向用例：只期望命中指定 code。"""
    COVERED.add(scope)
    with tempfile.TemporaryDirectory(prefix=f"dh-{scope}-") as tmp:
        root = copy_root(tmp)
        mutate(root)
        payload, rc = run_verify(root, scope)
        codes = codes_of(payload)
        if rc == 0 or expected_code not in codes:
            raise AssertionError(f"{name}: 期望 {expected_code}，实际 rc={rc} codes={codes}")
        print(f"PASS {name}: {expected_code}")


def stage_scope_case(name, scope_name, expected_code):
    """flow.json 里写一个未注册 scope，AGENTS.md 也照着写——仍必须报错。"""
    COVERED.add("gates")
    with tempfile.TemporaryDirectory(prefix="dh-stage-scope-") as tmp:
        root = copy_root(tmp)
        flow = read_json(root, ".harness/workflow/flow.json")
        flow["stages"][0]["scopes"].append(scope_name)
        write_json(root, ".harness/workflow/flow.json", flow)
        agents = root / "AGENTS.md"
        agents.write_text(
            agents.read_text(encoding="utf-8") + f"\n- `scope={scope_name}`\n", encoding="utf-8"
        )
        subprocess.run(
            [sys.executable, str(root / ".harness/scripts/gen_guide.py"), str(root)],
            check=True,
            capture_output=True,
        )
        payload, rc = run_verify(root, "gates")
        codes = codes_of(payload)
        if rc == 0 or expected_code not in codes:
            raise AssertionError(f"{name}: 期望 {expected_code}，实际 rc={rc} codes={codes}")
        print(f"PASS {name}: {expected_code}")


def ledger_line(scope, path, fingerprint, count):
    return f"{scope}\t{path}\t{fingerprint}\t{count}\n"


def ledger_fingerprint(code, message):
    """与 scopes/baseline.py 同一条规则：code + 消息里数字抹成 #。

    测试里再写一遍是有意的：这是**契约**，不是实现细节。规则改了而这里没改，
    降级/新欠的判定就会静默漂——那时应该让这里红，而不是让断言悄悄跟着实现走。
    """
    return f"{code}:{''.join('#' if ch.isdigit() else ch for ch in message or '')}"


def baseline_solo_case(name, scope, rel, code):
    """单查 baseline 不许编造建议：上游没跑时必须说「判不了」。

    它读的是其它 scope 已经报出来的 findings。`--scope baseline` 时上游是空集，
    「账本比现状多」会被算成正数——BASE014 于是把「上游没跑」误报成
    「老账已修掉一部分，可以刷新账本」。那是一条假建议，而刷新方式是手改文件。
    """
    COVERED.add("baseline")
    with tempfile.TemporaryDirectory(prefix="baseline-solo-") as tmp:
        root = copy_root(tmp)
        write_text(root, LEDGER_REL, ledger_line(scope, rel, f"{code}:x", 1))
        payload, _rc = run_verify(root, "baseline")
        codes = codes_of(payload)
        if "BASE014" in codes:
            raise AssertionError(
                f"{name}: 上游没跑却报 BASE014（假建议：老账已修掉一部分）。"
                "单查 baseline 时发现集恒为空，判定无从谈起")
        na = payload["summary"].get("not_applicable") or []
        if not any(str(item).startswith("baseline") for item in na):
            raise AssertionError(f"{name}: 单查 baseline 应记 not_applicable，实际 {na}")
        print(f"PASS {name}: 判不了，不冒充通过")


def notes_case(name, expected_code, setup):
    """notes scope 的反向测试：一篇笔记一个缺陷，期望恰好报那个 code。"""
    COVERED.add("notes")
    with tempfile.TemporaryDirectory(prefix="notes-") as tmp:
        root = copy_root(tmp)
        setup(root)
        subprocess.run(
            [sys.executable, str(root / ".harness/scripts/gen_guide.py"), str(root)],
            check=True,
            capture_output=True,
        )
        payload, rc = run_verify(root, "notes")
        codes = {f["code"] for f in payload["findings"] if f["severity"] == "ERROR"}
        if rc != 1 or codes != {expected_code}:
            raise AssertionError(f"{name}: 期望唯一 ERROR {expected_code}，实际 {sorted(codes)}，rc={rc}")
        print(f"PASS {name}: {expected_code}")


def baseline_error_case(name, expected_code, setup):
    """账本本身出错（格式 / 过期 / 只减不增）：只跑 baseline scope，期望唯一 ERROR。"""
    COVERED.add("baseline")
    with tempfile.TemporaryDirectory(prefix="go-base-") as tmp:
        root = copy_root(tmp)
        setup(root)
        payload, rc = run_verify(root, "baseline")
        codes = {finding["code"] for finding in payload["findings"]
                 if finding["severity"] == "ERROR"}
        if rc != 1 or codes != {expected_code}:
            raise AssertionError(
                f"{name}: 期望唯一的 ERROR 是 {expected_code}，实际 {sorted(codes)}，rc={rc}")
        print(f"PASS {name}: {expected_code}")


def baseline_behavior_case(name, defect_setup, scope, rel, code):
    """账本内 → 降级 WARN；账本外 → 仍是 ERROR 且前缀「新欠」。"""
    COVERED.add(scope)
    with tempfile.TemporaryDirectory(prefix="go-base-behavior-") as tmp:
        root = copy_root(tmp)
        defect_setup(root)
        # 改证据文件会让 codebase-guide 索引漂移，那是第二个缺陷：先同步回去
        subprocess.run(
            [sys.executable, str(root / ".harness/scripts/gen_guide.py"), str(root)],
            check=True, capture_output=True,
        )
        payload, rc = run_verify(root)
        hits = [f for f in payload["findings"]
                if f["severity"] == "ERROR" and f["code"] == code]
        if len(hits) != 1:
            raise AssertionError(f"{name}: 样本不干净，期望 1 条 {code}，实际 {len(hits)}")
        fingerprint = ledger_fingerprint(code, hits[0]["message"])

        write_text(root, LEDGER_REL, ledger_line(scope, rel, fingerprint, 1))
        payload, rc = run_verify(root)
        if rc != 0 or payload["summary"]["errors"] != 0:
            raise AssertionError(f"{name}: 账本内仍报 ERROR {payload['summary']['errors']} 条")
        kept = [f for f in payload["findings"] if f["code"] == code]
        if not kept or kept[0]["severity"] != "WARN" or not kept[0]["message"].startswith("基线内"):
            raise AssertionError(f"{name}: 账本内应降级为 WARN 且前缀「基线内」，实际 {kept}")

        write_text(root, LEDGER_REL, ledger_line(scope, rel, f"{code}:不存在的旧账", 1))
        payload, rc = run_verify(root)
        debt = [f for f in payload["findings"]
                if f["code"] == code and f["severity"] == "ERROR"]
        if rc != 1 or len(debt) != 1 or not debt[0]["message"].startswith("新欠"):
            raise AssertionError(f"{name}: 账本外应保持 ERROR 且前缀「新欠」，实际 {debt}")
        print(f"PASS {name}: 基线内 WARN / 新欠 ERROR")


def baseline_monotonic_case(name, scope, rel, code):
    """只减不增：旧账本已提交（total=1），涨到 2 必须 ERROR。没有 git 的场景另测。"""
    COVERED.add("baseline")
    with tempfile.TemporaryDirectory(prefix="go-base-mono-") as tmp:
        root = copy_root(tmp)
        line = ledger_line(scope, rel, f"{code}:旧账", 1)
        write_text(root, LEDGER_REL, line)
        git_init(root)
        write_text(root, LEDGER_REL, line + ledger_line(scope, rel, f"{code}:又一条", 1))
        payload, rc = run_verify(root, "baseline")
        codes = {f["code"] for f in payload["findings"] if f["severity"] == "ERROR"}
        if rc != 1 or codes != {"BASE013"}:
            raise AssertionError(f"{name}: 期望唯一 ERROR BASE013，实际 {sorted(codes)}，rc={rc}")
        print(f"PASS {name}: BASE013")



def main():
    positive_control()

    stage_scope_case("gates: stage.scopes 必须是已注册 scope", "ghost", "GATE001")
    text_reverse_case(
        "gates: AGENTS.md 规则编号必须连续",
        "AGENTS.md",
        lambda root: replace_text(root, "AGENTS.md", "10. 联调清单", "联调清单"),
        "gates",
        "GATE002",
    )
    reverse_case(
        "gates: required field 为 null 不当作已填",
        ".harness/deliverables/gates/01-requirements.json",
        lambda data: data.update({"owner": None}),
        "gates",
        "GATE003",
    )

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

    # --- baseline：账本自己也要被守 -----------------------------------------
    baseline_error_case(
        "baseline: 账本不是四列",
        "BASE011",
        lambda root: write_text(root, LEDGER_REL, "runtime\tinternal/order/service.go\tRUNT001:x\n"),
    )
    baseline_error_case(
        "baseline: accepted 缺负责人与复查日期",
        "BASE011",
        lambda root: write_text(
            root,
            ACCEPTED_REL,
            json.dumps([{"scope": "conf", "path": ".harness/config.json",
                         "fingerprint": "CONF001:x", "count": 1, "reason": "赶工"}],
                       ensure_ascii=False),
        ),
    )
    baseline_error_case(
        "baseline: accepted 的 reason/owner 不能为 null",
        "BASE011",
        lambda root: write_text(
            root,
            ACCEPTED_REL,
            json.dumps([{"scope": "conf", "path": ".harness/config.json",
                         "fingerprint": "CONF001:x", "count": 1, "reason": None,
                         "owner": None, "review_by": "2099-01-01"}], ensure_ascii=False),
        ),
    )
    baseline_error_case(
        "baseline: accepted 已过复查日期",
        "BASE012",
        lambda root: write_text(
            root,
            ACCEPTED_REL,
            json.dumps([{"scope": "conf", "path": ".harness/config.json",
                         "fingerprint": "CONF001:x", "count": 1, "reason": "赶工",
                         "owner": "reverse", "review_by": "2020-01-01"}], ensure_ascii=False),
        ),
    )
    baseline_behavior_case(
        "baseline: 账本内降级 / 账本外新欠",
        lambda root: write_json(
            root, ".harness/config.json",
            dict(read_json(root, ".harness/config.json"), task_max_daysx=3),
        ),
        "conf",
        ".harness/config.json",
        "CONF001",
    )
    reverse_case(
        "gates: 只有反思工单能写 stage='-'",
        ".harness/tasks/board.json",
        lambda d: d["tasks"].append(
            {
                "id": "T-999",
                "title": "手写工单却把 stage 写成 -",
                "owner": "dev-a",
                "stage": "-",
                "status": "todo",
                "updated": "2026-10-26",
                "origin": "manual",
            }
        ),
        "gates",
        "GATE007",
    )
    notes_case(
        "notes: 孤儿笔记（没人链进来）",
        "NTS001",
        lambda root: write_text(
            root,
            ".harness/specs/notes/proposed/2026-01-01-orphan.md",
            "---\ntitle: 没人引用的决策\ndate: 2026-01-01\nstatus: proposed\n"
            "scope: internal.order\nsummary: 写了但没有任何文档链进来\n---\n\n"
            "## 不显然之处\n\n这条只在当前文件里存在。\n",
        ),
    )
    notes_case(
        "notes: 状态与目录不一致",
        "NTS002",
        lambda root: (
            write_text(
                root,
                ".harness/specs/notes/implemented/2026-01-02-misplaced.md",
                "---\ntitle: 位置与字段对不上\ndate: 2026-01-02\nstatus: proposed\n"
                "scope: internal.order\nsummary: 目录说已落地，字段说还没拍\n---\n\n"
                "## 不显然之处\n\n状态是位置，字段只是投影。\n",
            ),
            write_text(
                root,
                ".harness/memory/decisions.md",
                "# 决策记录（全仓级）\n\n"
                "- 2026-01-02 位置与字段对不上（见 .harness/specs/notes/implemented/2026-01-02-misplaced.md）\n",
            ),
        ),
    )
    baseline_monotonic_case("baseline: 总数上升即 ERROR", "conf", ".harness/config.json", "CONF001")
    baseline_solo_case(
        "baseline: 单查不许编造「可以刷新账本」", "conf", ".harness/config.json", "CONF001"
    )
    evidence_age_case()

    registered = registered_scopes()
    missing = sorted(registered - COVERED)
    if missing:
        raise AssertionError(f"这些注册 scope 没有反向用例：{missing}（新增 scope 必须同批加一条）")
    print(f"PASS scope coverage: {len(COVERED)}/{len(registered)}")

    print("ALL REVERSE TESTS PASSED")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
