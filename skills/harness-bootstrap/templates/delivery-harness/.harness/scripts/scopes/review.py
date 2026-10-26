"""review: MR size, reviewer independence, comment closure, scans, merge state."""
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

NAME = "review"


def run(ctx, findings):
    rel = ".harness/deliverables/artifacts/review.json"
    data = load_json(ctx["root"], rel, NAME, findings, "REV001")
    if data is None:
        return
    if not isinstance(data, dict):
        add(findings, "ERROR", NAME, rel, 1, "REV001", "review.json 必须是对象")
        return
    warn_example(data, rel, NAME, findings, ctx["strict"])
    quality = as_dict(ctx.get("quality"))
    max_lines = quality_get(quality, "review_max_lines", 400)
    default_reviewers = quality_get(quality, "reviewers.default", 1)
    core_reviewers = quality_get(quality, "reviewers.core", 2)

    mrs = as_list(data.get("mrs"))
    if not mrs:
        add(findings, "ERROR", NAME, rel, 1, "REV002", "mrs 不能为空")
    for mr in mrs:
        if not isinstance(mr, dict):
            add(findings, "ERROR", NAME, rel, 1, "REV001", "MR 条目必须是对象")
            continue
        mid = mr.get("id", "?")
        check_fields(mr, ("id", "author", "lines_changed", "reviewers", "approvals"), NAME, rel, findings, "REV001", "mr.")
        lines = mr.get("lines_changed")
        if not num(lines):
            add(findings, "ERROR", NAME, rel, 1, "REV001", f"MR {mid!r} 的 lines_changed 必须是数字")
        elif lines > max_lines:
            if not (text(mr.get("split_justification")) and text(mr.get("approved_by"))):
                add(findings, "ERROR", NAME, rel, 1, "REV001",
                    f"MR {mid!r} 变更 {lines} 行 > {max_lines}，未拆分且无书面批准")
        reviewers = [r for r in as_list(mr.get("reviewers")) if text(r)]
        if mr.get("author") in reviewers:
            add(findings, "ERROR", NAME, rel, 1, "REV001", f"MR {mid!r} 作者不得自批")
        required = core_reviewers if mr.get("core") is True else default_reviewers
        if len(set(reviewers)) < required:
            add(findings, "ERROR", NAME, rel, 1, "REV002",
                f"MR {mid!r} 评审人不足：需要 {required}，实际 {len(set(reviewers))}")
        approvals = mr.get("approvals")
        if not num(approvals) or approvals < required:
            add(findings, "ERROR", NAME, rel, 1, "REV002",
                f"MR {mid!r} 审批数不足：需要 {required}，实际 {approvals!r}")
        if mr.get("comments_closed") is not True:
            add(findings, "ERROR", NAME, rel, 1, "REV002", f"MR {mid!r} 仍有未闭环意见")
        unresolved = as_dict(mr.get("unresolved"))
        for key in ("security", "performance", "correctness"):
            if unresolved.get(key, 0) != 0:
                add(findings, "ERROR", NAME, rel, 1, "REV003",
                    f"MR {mid!r} 仍有未解决 {key} 意见")
        if mr.get("ci") != "pass" or mr.get("sast") != "pass":
            add(findings, "ERROR", NAME, rel, 1, "REV003", f"MR {mid!r} CI/SAST 未通过")
        if mr.get("merged") is not True:
            add(findings, "ERROR", NAME, rel, 1, "REV003", f"MR {mid!r} 未合并")
