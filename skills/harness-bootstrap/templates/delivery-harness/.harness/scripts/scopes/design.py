"""design: design coverage, review discipline, frozen contract."""
from pathlib import Path

from .common import (
    add,
    as_dict,
    as_list,
    business_days_between,
    check_fields,
    load_json,
    parse_date,
    quality_get,
    text,
    warn_example,
)

NAME = "design"

REQUIRED_SECTIONS = {
    "modules",
    "boundaries",
    "data_flow",
    "schema",
    "third_party",
    "tech_selection",
    "api",
    "state_machine",
    "exceptions",
    "idempotency",
    "concurrency",
    "transactions",
    "security",
    "performance",
    "observability",
    "migration",
    "rollback",
    "compatibility",
    "test_strategy",
    "release",
}


def run(ctx, findings):
    rel = ".harness/deliverables/artifacts/design.json"
    data = load_json(ctx["root"], rel, NAME, findings, "DES001")
    if data is None:
        return
    if not isinstance(data, dict):
        add(findings, "ERROR", NAME, rel, 1, "DES001", "design.json 必须是对象")
        return
    warn_example(data, rel, NAME, findings, ctx["strict"])
    quality = as_dict(ctx.get("quality"))

    design = as_dict(data.get("design"))
    sections = set(as_list(design.get("sections")))
    missing = sorted(REQUIRED_SECTIONS - sections)
    if missing:
        add(findings, "ERROR", NAME, rel, 1, "DES002",
            f"方案缺少章节: {', '.join(missing)}")
    design_path = design.get("path")
    if not text(design_path) or not (Path(ctx["root"]) / design_path).is_file():
        add(findings, "ERROR", NAME, rel, 1, "DES002",
            f"design.path 不存在或为空: {design_path!r}")

    review = as_dict(data.get("review"))
    check_fields(review, ("doc_sent", "date", "participants", "conclusion"), NAME, rel, findings, "DES003", "review.")
    sent = parse_date(review.get("doc_sent"))
    meeting = parse_date(review.get("date"))
    lead_days = quality_get(quality, "doc_lead_business_days", 1)
    if sent is None or meeting is None:
        add(findings, "ERROR", NAME, rel, 1, "DES003", "review.doc_sent/date 不是 YYYY-MM-DD")
    elif business_days_between(sent, meeting) < lead_days:
        add(findings, "ERROR", NAME, rel, 1, "DES003",
            f"方案发出到评审不足 {lead_days} 个工作日")

    participants = set(as_list(review.get("participants")))
    if not {"PO", "Dev", "QA", "Arch"} <= participants:
        add(findings, "ERROR", NAME, rel, 1, "DES003",
            "评审参与方必须包含 PO/Dev/QA/Arch")
    if review.get("security_required") is True and "Sec" not in participants:
        add(findings, "ERROR", NAME, rel, 1, "DES003", "需要安全评审但缺少 Sec")
    if review.get("db_change") is True and "DBA" not in participants:
        add(findings, "ERROR", NAME, rel, 1, "DES003", "涉及数据库变更但缺少 DBA")
    if review.get("ops_change") is True and "Ops" not in participants:
        add(findings, "ERROR", NAME, rel, 1, "DES003", "涉及部署/配置变更但缺少 Ops")

    conclusion = review.get("conclusion")
    if conclusion not in ("pass", "modified", "rejected"):
        add(findings, "ERROR", NAME, rel, 1, "DES003",
            f"review.conclusion 必须是 pass/modified/rejected，实际 {conclusion!r}")
    issues = as_list(review.get("issues"))
    if conclusion in ("modified", "rejected") and not issues:
        add(findings, "ERROR", NAME, rel, 1, "DES003", f"{conclusion} 必须有问题清单")
    open_issues = 0
    for issue in issues:
        if not isinstance(issue, dict):
            add(findings, "ERROR", NAME, rel, 1, "DES003", "issue 条目必须是对象")
            continue
        check_fields(issue, ("id", "owner", "deadline", "status"), NAME, rel, findings, "DES003", "issue.")
        if issue.get("status") != "closed":
            open_issues += 1
        if parse_date(issue.get("deadline")) is None:
            add(findings, "ERROR", NAME, rel, 1, "DES003",
                f"issue {issue.get('id', '?')} 的 deadline 不是 YYYY-MM-DD")
    if conclusion == "pass" and open_issues:
        add(findings, "ERROR", NAME, rel, 1, "DES003", "结论为 pass 但仍有未关闭问题")
    if conclusion == "modified":
        re_review = parse_date(review.get("re_review_date"))
        limit = quality_get(quality, "re_review_business_days", 2)
        if re_review is None or meeting is None:
            add(findings, "ERROR", NAME, rel, 1, "DES003",
                "修改后通过必须写 re_review_date（YYYY-MM-DD）")
        elif business_days_between(meeting, re_review) > limit:
            add(findings, "ERROR", NAME, rel, 1, "DES003",
                f"复评超过 {limit} 个工作日")
    if conclusion == "rejected":
        add(findings, "ERROR", NAME, rel, 1, "DES003", "方案被驳回，不得进入开发")

    contract = as_dict(data.get("contract"))
    check_fields(contract, ("version", "fields", "error_codes", "signed_by"), NAME, rel, findings, "DES004", "contract.")
    if not {"FE", "BE", "QA"} <= set(as_list(contract.get("signed_by"))):
        add(findings, "ERROR", NAME, rel, 1, "DES004",
            "契约签字必须包含 FE/BE/QA")
    if text(design.get("version")) and text(contract.get("version")) and design.get("version") != contract.get("version"):
        add(findings, "ERROR", NAME, rel, 1, "DES004",
            "design.version 与 contract.version 不一致")
