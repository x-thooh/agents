"""review: 代码评审门（artifacts/review.json）：体量、评审人、自批、意见闭环。"""
from pathlib import Path

from .common import add, as_dict, as_list, check_fields, load_json, num, quality_get, text, warn_example

NAME = "review"
REL = ".harness/deliverables/artifacts/review.json"


def run(ctx, findings):
    data = load_json(Path(ctx["root"]), REL, NAME, findings, "REV001")
    if not isinstance(data, dict):
        return
    warn_example(data, REL, NAME, findings, ctx["strict"])
    mrs = as_list(data.get("mrs"))
    if not mrs:
        add(findings, "ERROR", NAME, REL, 1, "REV001", "mrs 不能为空：本阶段至少要有一份已评审的 MR")
        return
    quality = as_dict(ctx.get("quality"))
    for mr in mrs:
        if not isinstance(mr, dict):
            add(findings, "ERROR", NAME, REL, 1, "REV001", "mrs 条目必须是对象")
            continue
        check_fields(mr, ("id", "title", "author", "lines_changed", "reviewers", "approvals", "comments"),
                     NAME, REL, findings, "REV001", f"mr {mr.get('id', '?')}.")
        check_size(mr, quality, findings)
        check_people(mr, quality, findings)
        check_comments(mr, findings)


def check_size(mr, quality, findings):
    limit = quality_get(quality, "review.max_lines", 400)
    changed = mr.get("lines_changed")
    if not num(changed):
        add(findings, "ERROR", NAME, REL, 1, "REV001", f"mr {mr.get('id', '?')} 的 lines_changed 不是数字")
        return
    if changed > limit and mr.get("oversize_approved") is not True:
        add(findings, "ERROR", NAME, REL, 1, "REV001",
            f"mr {mr.get('id', '?')} 改了 {changed} 行，超过 {limit}；拆分或标 oversize_approved + 批准人")


def check_people(mr, quality, findings):
    author = mr.get("author")
    reviewers = [r for r in as_list(mr.get("reviewers")) if text(r)]
    approvals = [a for a in as_list(mr.get("approvals")) if text(a)]
    minimum = quality_get(quality, "review.min_reviewers", 2)
    if len(reviewers) < minimum:
        add(findings, "ERROR", NAME, REL, 1, "REV003",
            f"mr {mr.get('id', '?')} 只有 {len(reviewers)} 名评审人，要求至少 {minimum}")
    if text(author) and author in approvals:
        add(findings, "ERROR", NAME, REL, 1, "REV002",
            f"mr {mr.get('id', '?')} 作者 {author} 出现在 approvals：不得自批")
    missing = [r for r in reviewers if r not in approvals]
    if missing:
        add(findings, "ERROR", NAME, REL, 1, "REV003",
            f"mr {mr.get('id', '?')} 的评审人未签字: {missing}")


def check_comments(mr, findings):
    comments = as_list(mr.get("comments"))
    if not comments:
        add(findings, "WARN", NAME, REL, 1, "REV004",
            f"mr {mr.get('id', '?')} 没有任何评审意见：要么没人看，要么没记录")
        return
    for comment in comments:
        if not isinstance(comment, dict):
            add(findings, "ERROR", NAME, REL, 1, "REV004", "comments 条目必须是对象")
            continue
        if not text(comment.get("id")):
            add(findings, "ERROR", NAME, REL, 1, "REV004", "评审意见缺 id")
        if comment.get("status") != "closed":
            add(findings, "ERROR", NAME, REL, 1, "REV004",
                f"评审意见 {comment.get('id', '?')} 未闭环（status={comment.get('status')!r}）")
