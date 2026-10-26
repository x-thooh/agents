"""selftest: checklist execution, pass rate, defect triage, submission readiness."""
from pathlib import Path

from .common import (
    add,
    as_dict,
    as_list,
    check_fields,
    load_json,
    num,
    parse_date,
    quality_get,
    text,
    warn_example,
)

NAME = "selftest"


def run(ctx, findings):
    rel = ".harness/deliverables/artifacts/selftest.json"
    data = load_json(ctx["root"], rel, NAME, findings, "ST001")
    if data is None:
        return
    if not isinstance(data, dict):
        add(findings, "ERROR", NAME, rel, 1, "ST001", "selftest.json 必须是对象")
        return
    warn_example(data, rel, NAME, findings, ctx["strict"])
    quality = as_dict(ctx.get("quality"))

    checklist = as_list(data.get("checklist"))
    if not checklist:
        add(findings, "ERROR", NAME, rel, 1, "ST002", "checklist 不能为空")
    for item in checklist:
        if not isinstance(item, dict):
            add(findings, "ERROR", NAME, rel, 1, "ST002", "checklist 条目必须是对象")
            continue
        check_fields(item, ("id", "feature", "status", "evidence"), NAME, rel, findings, "ST002", "checklist.")
        if item.get("status") != "pass":
            add(findings, "ERROR", NAME, rel, 1, "ST002",
                f"自测项 {item.get('id', '?')} 未通过")

    if data.get("execution_rate") != 100:
        add(findings, "ERROR", NAME, rel, 1, "ST002",
            f"execution_rate 必须为 100，实际 {data.get('execution_rate')!r}")
    pass_rate = data.get("pass_rate")
    minimum = quality_get(quality, "selftest_pass_rate", 95)
    if not num(pass_rate):
        add(findings, "ERROR", NAME, rel, 1, "ST002", "pass_rate 必须是数字")
    elif pass_rate < minimum:
        add(findings, "ERROR", NAME, rel, 1, "ST002",
            f"pass_rate={pass_rate} 低于阈值 {minimum}")

    defects = as_dict(data.get("defects"))
    if defects.get("P0", 0) != 0 or defects.get("P1", 0) != 0:
        add(findings, "ERROR", NAME, rel, 1, "ST001",
            "自测遗留 P0/P1 缺陷，不得提测")
    for defect in as_list(data.get("defect_details")):
        if not isinstance(defect, dict):
            add(findings, "ERROR", NAME, rel, 1, "ST001", "defect 条目必须是对象")
            continue
        check_fields(defect, ("id", "severity", "owner", "deadline"), NAME, rel, findings, "ST001", "defect.")
        if defect.get("severity") in ("P0", "P1"):
            add(findings, "ERROR", NAME, rel, 1, "ST001",
                f"缺陷 {defect.get('id', '?')} 仍是 {defect.get('severity')}")
        if parse_date(defect.get("deadline")) is None:
            add(findings, "ERROR", NAME, rel, 1, "ST001",
                f"缺陷 {defect.get('id', '?')} 的 deadline 不是 YYYY-MM-DD")

    ready = as_dict(data.get("submission_ready"))
    for key in ("package", "env_deployed", "smoke_ready", "rollback_tested"):
        if ready.get(key) is not True:
            add(findings, "ERROR", NAME, rel, 1, "ST003",
                f"submission_ready.{key} 必须为 true")

    report = data.get("report")
    if not text(report) or not (Path(ctx["root"]) / report).is_file():
        add(findings, "ERROR", NAME, rel, 1, "ST003", f"report 不存在或为空: {report!r}")
