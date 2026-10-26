"""requirements: PRD baseline, NFR, task cards, traceability, impact."""
from .common import (
    add,
    as_dict,
    as_list,
    check_fields,
    has_cycle,
    load_json,
    num,
    quality_get,
    text,
    warn_example,
)

NAME = "requirements"
PRIORITIES = {"P0", "P1", "P2", "P3"}
NFR_CATEGORIES = {"performance", "security", "observability", "compatibility"}


def run(ctx, findings):
    rel = ".harness/deliverables/artifacts/requirements.json"
    data = load_json(ctx["root"], rel, NAME, findings, "REQ001")
    if data is None:
        return
    if not isinstance(data, dict):
        add(findings, "ERROR", NAME, rel, 1, "REQ001", "requirements.json 必须是对象")
        return
    warn_example(data, rel, NAME, findings, ctx["strict"])
    max_days = quality_get(as_dict(ctx.get("quality")), "task_max_days", 3)

    prd = as_dict(data.get("prd"))
    check_fields(prd, ("version", "hash", "signed_by"), NAME, rel, findings, "REQ002", "prd.")
    if not {"PO", "QA", "Arch"} <= set(as_list(prd.get("signed_by"))):
        add(findings, "ERROR", NAME, rel, 1, "REQ002",
            "PRD 签字必须包含 PO/QA/Arch")

    requirements = as_list(data.get("requirements"))
    if not requirements:
        add(findings, "ERROR", NAME, rel, 1, "REQ004", "requirements 不能为空")
    req_ids = set()
    for req in requirements:
        if not isinstance(req, dict):
            add(findings, "ERROR", NAME, rel, 1, "REQ004", "requirement 条目必须是对象")
            continue
        check_fields(
            req,
            ("id", "acceptance", "priority", "target", "owner"),
            NAME,
            rel,
            findings,
            "REQ004",
            "requirement.",
        )
        rid = req.get("id")
        if rid in req_ids:
            add(findings, "ERROR", NAME, rel, 1, "REQ004", f"requirement id 重复: {rid!r}")
        req_ids.add(rid)
        if req.get("priority") not in PRIORITIES:
            add(findings, "ERROR", NAME, rel, 1, "REQ004",
                f"requirement {rid!r} 的 priority 不在 {sorted(PRIORITIES)}")

    nfr = as_list(data.get("nfr"))
    if not nfr:
        add(findings, "ERROR", NAME, rel, 1, "REQ004", "nfr 不能为空")
    categories = set()
    for item in nfr:
        if not isinstance(item, dict):
            add(findings, "ERROR", NAME, rel, 1, "REQ004", "nfr 条目必须是对象")
            continue
        check_fields(
            item,
            ("id", "category", "metric", "verification"),
            NAME,
            rel,
            findings,
            "REQ004",
            "nfr.",
        )
        categories.add(item.get("category"))
    for category in sorted(NFR_CATEGORIES):
        if category not in categories:
            add(findings, "ERROR", NAME, rel, 1, "REQ004", f"NFR 缺少类别: {category}")

    tasks = as_list(data.get("tasks"))
    if not tasks:
        add(findings, "ERROR", NAME, rel, 1, "REQ003", "tasks 不能为空")
    task_ids = set()
    graph = {}
    for task in tasks:
        if not isinstance(task, dict):
            add(findings, "ERROR", NAME, rel, 1, "REQ003", "task 条目必须是对象")
            continue
        check_fields(
            task,
            ("id", "title", "owner", "estimate_days"),
            NAME,
            rel,
            findings,
            "REQ003",
            "task.",
        )
        tid = task.get("id")
        if tid in task_ids:
            add(findings, "ERROR", NAME, rel, 1, "REQ003", f"task id 重复: {tid!r}")
        task_ids.add(tid)
        estimate = task.get("estimate_days")
        if not num(estimate) or estimate < 1 or estimate > max_days:
            add(findings, "ERROR", NAME, rel, 1, "REQ003",
                f"task {tid!r} 的 estimate_days 必须在 1–{max_days} 人天，实际 {estimate!r}")
        graph[tid] = [dep for dep in as_list(task.get("depends_on")) if text(dep)]
    for tid, deps in graph.items():
        for dep in deps:
            if dep not in task_ids:
                add(findings, "ERROR", NAME, rel, 1, "REQ003",
                    f"task {tid!r} 依赖不存在的 task {dep!r}")
    if has_cycle(graph):
        add(findings, "ERROR", NAME, rel, 1, "REQ003", "task 依赖存在环")

    traceability = as_list(data.get("traceability"))
    if not traceability:
        add(findings, "ERROR", NAME, rel, 1, "REQ004", "traceability 不能为空")
    traced = set()
    for row in traceability:
        if not isinstance(row, dict):
            add(findings, "ERROR", NAME, rel, 1, "REQ004", "traceability 条目必须是对象")
            continue
        check_fields(
            row,
            ("requirement", "tasks", "tests"),
            NAME,
            rel,
            findings,
            "REQ004",
            "traceability.",
        )
        rid = row.get("requirement")
        if rid not in req_ids:
            add(findings, "ERROR", NAME, rel, 1, "REQ004",
                f"traceability 指向不存在的 requirement {rid!r}")
        traced.add(rid)
        for tid in as_list(row.get("tasks")):
            if tid not in task_ids:
                add(findings, "ERROR", NAME, rel, 1, "REQ004",
                    f"traceability 指向不存在的 task {tid!r}")
    for rid in sorted(req_ids):
        if rid not in traced:
            add(findings, "ERROR", NAME, rel, 1, "REQ004",
                f"requirement {rid!r} 没有进入跟踪矩阵")

    impact = as_dict(data.get("impact"))
    for key in ("modules", "interfaces", "existing_features"):
        if not as_list(impact.get(key)):
            add(findings, "ERROR", NAME, rel, 1, "REQ004", f"impact.{key} 不能为空")
