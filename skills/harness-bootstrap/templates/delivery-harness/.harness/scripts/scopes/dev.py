"""dev: task completion, unit tests, coverage, CI/SAST/build, commit hygiene."""
import re

from .common import (
    add,
    as_dict,
    as_list,
    check_fields,
    load_json,
    num,
    quality_get,
    text,
    warn_example,
)

NAME = "dev"
COMMIT_RE = re.compile(r"^(feat|fix|refactor|test|docs|chore)(\([a-z0-9._-]+\))?: .+")


def run(ctx, findings):
    rel = ".harness/deliverables/artifacts/dev.json"
    data = load_json(ctx["root"], rel, NAME, findings, "DEV001")
    if data is None:
        return
    if not isinstance(data, dict):
        add(findings, "ERROR", NAME, rel, 1, "DEV001", "dev.json 必须是对象")
        return
    warn_example(data, rel, NAME, findings, ctx["strict"])
    quality = as_dict(ctx.get("quality"))

    coverage = as_dict(data.get("coverage"))
    thresholds = (
        ("core", quality_get(quality, "coverage.core_min", 60)),
        ("noncore", quality_get(quality, "coverage.noncore_min", 40)),
        ("new_code", quality_get(quality, "coverage.new_code_min", 80)),
    )
    for key, minimum in thresholds:
        value = coverage.get(key)
        if not num(value):
            add(findings, "ERROR", NAME, rel, 1, "DEV002", f"coverage.{key} 必须是数字")
        elif value < minimum:
            add(findings, "ERROR", NAME, rel, 1, "DEV002",
                f"coverage.{key}={value} 低于阈值 {minimum}")

    tests = as_dict(data.get("unit_tests"))
    total = tests.get("total")
    passed = tests.get("passed")
    failed = tests.get("failed")
    if not num(total) or total <= 0:
        add(findings, "ERROR", NAME, rel, 1, "DEV003", "unit_tests.total 必须 > 0")
    if not num(failed) or failed != 0:
        add(findings, "ERROR", NAME, rel, 1, "DEV003", f"unit_tests.failed 必须为 0，实际 {failed!r}")
    if not num(passed) or not num(total) or passed != total:
        add(findings, "ERROR", NAME, rel, 1, "DEV003",
            f"unit_tests.passed 必须等于 total（{passed!r} != {total!r}）")

    ci = as_dict(data.get("ci"))
    if ci.get("status") != "pass":
        add(findings, "ERROR", NAME, rel, 1, "DEV003", "ci.status 必须为 pass")
    if not text(ci.get("url")):
        add(findings, "ERROR", NAME, rel, 1, "DEV003", "ci.url 不能为空")

    sast = as_dict(data.get("sast"))
    if sast.get("status") != "pass":
        add(findings, "ERROR", NAME, rel, 1, "DEV003", "sast.status 必须为 pass")
    if sast.get("blockers", 0) != 0:
        add(findings, "ERROR", NAME, rel, 1, "DEV003", "sast.blockers 必须为 0")

    build = as_dict(data.get("build"))
    if build.get("status") != "pass":
        add(findings, "ERROR", NAME, rel, 1, "DEV003", "build.status 必须为 pass")
    if build.get("warnings_blocking", 0) != 0:
        add(findings, "ERROR", NAME, rel, 1, "DEV003", "build.warnings_blocking 必须为 0")

    tasks = as_list(data.get("tasks"))
    if not tasks:
        add(findings, "ERROR", NAME, rel, 1, "DEV004", "tasks 不能为空")
    task_ids = set()
    for task in tasks:
        if not isinstance(task, dict):
            add(findings, "ERROR", NAME, rel, 1, "DEV004", "task 条目必须是对象")
            continue
        check_fields(task, ("id", "status", "acceptance_met"), NAME, rel, findings, "DEV004", "task.")
        task_ids.add(task.get("id"))
        if task.get("status") != "done":
            add(findings, "ERROR", NAME, rel, 1, "DEV004",
                f"task {task.get('id', '?')} 未完成（status={task.get('status')!r}）")
        if task.get("acceptance_met") is not True:
            add(findings, "ERROR", NAME, rel, 1, "DEV004",
                f"task {task.get('id', '?')} 未声明验收标准满足")

    commits = as_list(data.get("commits"))
    if not commits:
        add(findings, "ERROR", NAME, rel, 1, "DEV004", "commits 不能为空")
    seen = set()
    for commit in commits:
        if not isinstance(commit, dict):
            add(findings, "ERROR", NAME, rel, 1, "DEV004", "commit 条目必须是对象")
            continue
        check_fields(commit, ("hash", "message"), NAME, rel, findings, "DEV004", "commit.")
        digest = commit.get("hash")
        if digest in seen:
            add(findings, "ERROR", NAME, rel, 1, "DEV004", f"commit hash 重复: {digest!r}")
        seen.add(digest)
        message = commit.get("message")
        if not text(message) or not COMMIT_RE.match(message):
            add(findings, "ERROR", NAME, rel, 1, "DEV004",
                f"commit {digest!r} 的 message 不符合 type(scope): subject")
        task = commit.get("task")
        if text(task):
            if task_ids and task not in task_ids:
                add(findings, "ERROR", NAME, rel, 1, "DEV004",
                    f"commit {digest!r} 关联了不存在的 task {task!r}")
        elif not any(tid and tid in (message or "") for tid in task_ids):
            add(findings, "ERROR", NAME, rel, 1, "DEV004",
                f"commit {digest!r} 未关联有效 task")

    flags = as_dict(data.get("feature_flags"))
    if flags and flags.get("default_safe") is not True:
        add(findings, "ERROR", NAME, rel, 1, "DEV004", "feature_flags.default_safe 必须为 true")
