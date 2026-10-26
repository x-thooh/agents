"""coherence: E2E chains, data consistency, PRD traceability, regression, NFR."""
from .common import (
    add,
    as_dict,
    as_list,
    check_fields,
    load_json,
    text,
    warn_example,
)

NAME = "coherence"


def run(ctx, findings):
    rel = ".harness/deliverables/artifacts/coherence.json"
    data = load_json(ctx["root"], rel, NAME, findings, "COH001")
    if data is None:
        return
    if not isinstance(data, dict):
        add(findings, "ERROR", NAME, rel, 1, "COH001", "coherence.json 必须是对象")
        return
    warn_example(data, rel, NAME, findings, ctx["strict"])

    e2e = as_list(data.get("e2e"))
    if not e2e:
        add(findings, "ERROR", NAME, rel, 1, "COH002", "e2e 不能为空")
    for item in e2e:
        if not isinstance(item, dict):
            add(findings, "ERROR", NAME, rel, 1, "COH002", "e2e 条目必须是对象")
            continue
        check_fields(item, ("id", "chain", "status", "evidence"), NAME, rel, findings, "COH002", "e2e.")
        if item.get("status") != "pass":
            add(findings, "ERROR", NAME, rel, 1, "COH002",
                f"E2E {item.get('id', '?')} 未通过")

    consistency = as_list(data.get("data_consistency"))
    if not consistency:
        add(findings, "ERROR", NAME, rel, 1, "COH003", "data_consistency 不能为空")
    for item in consistency:
        if not isinstance(item, dict):
            add(findings, "ERROR", NAME, rel, 1, "COH003", "data_consistency 条目必须是对象")
            continue
        check_fields(item, ("id", "status", "evidence"), NAME, rel, findings, "COH003", "data_consistency.")
        if item.get("status") != "pass":
            add(findings, "ERROR", NAME, rel, 1, "COH003",
                f"数据一致性 {item.get('id', '?')} 未通过")

    req_data = load_json(
        ctx["root"], ".harness/deliverables/artifacts/requirements.json", NAME, findings, "COH001"
    )
    req_ids = None
    nfr_ids = None
    if isinstance(req_data, dict):
        req_ids = {
            item.get("id")
            for item in as_list(req_data.get("requirements"))
            if isinstance(item, dict) and text(item.get("id"))
        }
        nfr_ids = {
            item.get("id")
            for item in as_list(req_data.get("nfr"))
            if isinstance(item, dict) and text(item.get("id"))
        }

    traceability = as_list(data.get("traceability"))
    if not traceability:
        add(findings, "ERROR", NAME, rel, 1, "COH002", "traceability 不能为空")
    traced = set()
    for row in traceability:
        if not isinstance(row, dict):
            add(findings, "ERROR", NAME, rel, 1, "COH002", "traceability 条目必须是对象")
            continue
        check_fields(row, ("requirement", "status", "evidence"), NAME, rel, findings, "COH002", "traceability.")
        rid = row.get("requirement")
        if req_ids is not None and rid not in req_ids:
            add(findings, "ERROR", NAME, rel, 1, "COH002",
                f"traceability 指向不存在的 requirement {rid!r}")
        if row.get("status") != "pass":
            add(findings, "ERROR", NAME, rel, 1, "COH002",
                f"requirement {rid!r} 自洽验证未通过")
        if not as_list(row.get("evidence")):
            add(findings, "ERROR", NAME, rel, 1, "COH002",
                f"requirement {rid!r} 没有证据")
        traced.add(rid)
    if req_ids is not None:
        for rid in sorted(req_ids):
            if rid not in traced:
                add(findings, "ERROR", NAME, rel, 1, "COH002",
                    f"requirement {rid!r} 未进入自洽跟踪矩阵")

    nfr_results = {}
    for item in as_list(data.get("nfr")):
        if not isinstance(item, dict):
            add(findings, "ERROR", NAME, rel, 1, "COH003", "nfr 结果条目必须是对象")
            continue
        check_fields(item, ("id", "status", "evidence"), NAME, rel, findings, "COH003", "nfr.")
        nfr_results[item.get("id")] = item
        if item.get("status") != "pass":
            add(findings, "ERROR", NAME, rel, 1, "COH003",
                f"NFR {item.get('id', '?')} 未通过")
    if nfr_ids is not None:
        for nid in sorted(nfr_ids):
            result = nfr_results.get(nid)
            if result is None:
                add(findings, "ERROR", NAME, rel, 1, "COH003", f"NFR {nid!r} 没有验收结果")
            elif not text(result.get("evidence")):
                add(findings, "ERROR", NAME, rel, 1, "COH003", f"NFR {nid!r} 没有证据")

    regression = as_dict(data.get("regression"))
    if regression.get("status") != "pass":
        add(findings, "ERROR", NAME, rel, 1, "COH003", "regression.status 必须为 pass")
    if not as_list(regression.get("scope")):
        add(findings, "ERROR", NAME, rel, 1, "COH003", "regression.scope 不能为空")
    if regression.get("new_p0_p1", 0) != 0:
        add(findings, "ERROR", NAME, rel, 1, "COH003", "回归出现新的 P0/P1")

    for issue in as_list(data.get("known_issues")):
        if not isinstance(issue, dict):
            add(findings, "ERROR", NAME, rel, 1, "COH003", "known_issue 条目必须是对象")
            continue
        check_fields(issue, ("id", "severity", "owner", "deadline"), NAME, rel, findings, "COH003", "known_issue.")
        if issue.get("severity") in ("P0", "P1"):
            add(findings, "ERROR", NAME, rel, 1, "COH003",
                f"已知问题 {issue.get('id', '?')} 仍是 {issue.get('severity')}")
