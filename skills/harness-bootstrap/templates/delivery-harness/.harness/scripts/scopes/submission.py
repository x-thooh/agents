"""submission: package manifest, smoke test, version alignment, QA acceptance."""
from .common import (
    add,
    as_dict,
    check_fields,
    load_json,
    num,
    quality_get,
    text,
    warn_example,
)

NAME = "submission"

MANIFEST_KEYS = (
    "submission_form",
    "api_change",
    "db_change",
    "db_rollback",
    "config_change",
    "selftest_report",
    "known_issues",
    "deployment",
    "test_data",
    "env_baseline",
    "risk_list",
)


def run(ctx, findings):
    rel = ".harness/deliverables/artifacts/submission.json"
    data = load_json(ctx["root"], rel, NAME, findings, "SUB001")
    if data is None:
        return
    if not isinstance(data, dict):
        add(findings, "ERROR", NAME, rel, 1, "SUB001", "submission.json 必须是对象")
        return
    warn_example(data, rel, NAME, findings, ctx["strict"])

    manifest = as_dict(data.get("manifest"))
    check_fields(manifest, MANIFEST_KEYS, NAME, rel, findings, "SUB001", "manifest.")
    if text(manifest.get("db_change")) and manifest.get("db_change") != "N/A":
        if not text(manifest.get("db_rollback")):
            add(findings, "ERROR", NAME, rel, 1, "SUB001",
                "有数据库变更但缺少 db_rollback")

    smoke = as_dict(data.get("smoke"))
    total = smoke.get("total")
    passed = smoke.get("passed")
    if smoke.get("status") != "pass":
        add(findings, "ERROR", NAME, rel, 1, "SUB002", "smoke.status 必须为 pass")
    if not num(total) or total <= 0:
        add(findings, "ERROR", NAME, rel, 1, "SUB002", "smoke.total 必须 > 0")
    if not num(passed) or not num(total) or passed != total:
        add(findings, "ERROR", NAME, rel, 1, "SUB002",
            f"smoke.passed 必须等于 total（{passed!r} != {total!r}）")
    if num(passed) and num(total) and total > 0:
        rate = passed / total * 100
        minimum = quality_get(as_dict(ctx.get("quality")), "smoke_pass_rate", 100)
        if rate < minimum:
            add(findings, "ERROR", NAME, rel, 1, "SUB002",
                f"冒烟通过率 {rate:g}% 低于阈值 {minimum}%")
    if not text(smoke.get("executor")):
        add(findings, "ERROR", NAME, rel, 1, "SUB002", "smoke.executor 不能为空")

    version = as_dict(data.get("version"))
    check_fields(version, ("tag", "commit", "test_env"), NAME, rel, findings, "SUB003", "version.")
    tag = version.get("tag")
    test_env = version.get("test_env")
    if text(tag) and text(test_env) and test_env != tag and not test_env.startswith(tag):
        add(findings, "ERROR", NAME, rel, 1, "SUB003",
            f"测试环境版本 {test_env!r} 与 tag {tag!r} 不一致")

    if data.get("qa_accepted") is not True:
        add(findings, "ERROR", NAME, rel, 1, "SUB003", "qa_accepted 必须为 true")
    if data.get("rollback_tested") is not True:
        add(findings, "ERROR", NAME, rel, 1, "SUB003", "rollback_tested 必须为 true")

    defects = as_dict(data.get("defects"))
    if defects.get("P0", 0) != 0 or defects.get("P1", 0) != 0:
        add(findings, "ERROR", NAME, rel, 1, "SUB003", "提测遗留 P0/P1 缺陷")
