"""integration: interface checklist, contract tests, environment parity, changes."""
from .common import (
    add,
    as_dict,
    as_list,
    check_fields,
    load_json,
    num,
    text,
    validate_change,
    warn_example,
)

NAME = "integration"

REQUIRED_VALIDATIONS = {
    "fields",
    "nulls",
    "enums",
    "boundaries",
    "error_codes",
    "pagination",
    "auth",
    "timeout",
    "retry",
    "idempotency",
    "rate_limit",
    "degradation",
    "logging",
    "trace_id",
}


def run(ctx, findings):
    rel = ".harness/deliverables/artifacts/integration.json"
    data = load_json(ctx["root"], rel, NAME, findings, "INT001")
    if data is None:
        return
    if not isinstance(data, dict):
        add(findings, "ERROR", NAME, rel, 1, "INT001", "integration.json 必须是对象")
        return
    warn_example(data, rel, NAME, findings, ctx["strict"])

    interfaces = as_list(data.get("interfaces"))
    if not interfaces:
        add(findings, "ERROR", NAME, rel, 1, "INT001", "interfaces 不能为空")
    for interface in interfaces:
        if not isinstance(interface, dict):
            add(findings, "ERROR", NAME, rel, 1, "INT001", "interface 条目必须是对象")
            continue
        check_fields(interface, ("id", "status", "validated"), NAME, rel, findings, "INT001", "interface.")
        iid = interface.get("id")
        if interface.get("status") != "pass":
            add(findings, "ERROR", NAME, rel, 1, "INT001",
                f"interface {iid!r} 未通过（status={interface.get('status')!r}）")
        missing = sorted(REQUIRED_VALIDATIONS - set(as_list(interface.get("validated"))))
        if missing:
            add(findings, "ERROR", NAME, rel, 1, "INT001",
                f"interface {iid!r} 缺少验证项: {', '.join(missing)}")

    tests = as_dict(data.get("contract_tests"))
    total = tests.get("total")
    passed = tests.get("passed")
    if tests.get("status") != "pass":
        add(findings, "ERROR", NAME, rel, 1, "INT002", "contract_tests.status 必须为 pass")
    if not num(total) or total <= 0:
        add(findings, "ERROR", NAME, rel, 1, "INT002", "contract_tests.total 必须 > 0")
    if not num(passed) or not num(total) or passed != total:
        add(findings, "ERROR", NAME, rel, 1, "INT002",
            f"contract_tests.passed 必须等于 total（{passed!r} != {total!r}）")

    env = as_dict(data.get("env"))
    check_fields(env, ("integration", "test"), NAME, rel, findings, "INT003", "env.")
    if env.get("integration") != env.get("test") and (
            not text(env.get("diff")) or env.get("diff_approved") is not True):
        add(findings, "ERROR", NAME, rel, 1, "INT003",
            "联调与测试环境版本不一致，且没有书面差异或批准")

    changes = as_list(data.get("changes"))
    for change in changes:
        if not isinstance(change, dict):
            add(findings, "ERROR", NAME, rel, 1, "INT004", "change 条目必须是对象")
            continue
        validate_change(change, NAME, rel, findings, "INT004")
        if change.get("type") != "contract":
            add(findings, "ERROR", NAME, rel, 1, "INT004",
                f"联调阶段变更 {change.get('id', '?')} 的 type 必须是 contract")
        if len(as_list(change.get("notified"))) < 2:
            add(findings, "ERROR", NAME, rel, 1, "INT004",
                f"契约变更 {change.get('id', '?')} 必须通知上下游两方")

    defects = as_dict(data.get("defects"))
    if defects.get("P0", 0) != 0 or defects.get("P1", 0) != 0:
        add(findings, "ERROR", NAME, rel, 1, "INT004",
            "联调遗留 P0/P1 缺陷，不得进入自测")
