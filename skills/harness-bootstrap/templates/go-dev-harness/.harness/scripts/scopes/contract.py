"""contract: 需求与接口契约证据（artifacts/contract.json）。"""
from pathlib import Path

from .common import add, as_dict, as_list, check_fields, load_json, text, warn_example

NAME = "contract"
REL = ".harness/deliverables/artifacts/contract.json"
METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
NFR_KEYS = ("performance", "observability", "compatibility")


def run(ctx, findings):
    data = load_json(Path(ctx["root"]), REL, NAME, findings, "CTR001")
    if not isinstance(data, dict):
        return
    warn_example(data, REL, NAME, findings, ctx["strict"])
    check_fields(data, ("id", "title", "acceptance", "interfaces", "nfr"), NAME, REL, findings, "CTR001")
    check_acceptance(data, findings)
    check_interfaces(data, findings)
    check_nfr(data, findings)


def check_acceptance(data, findings):
    for item in as_list(data.get("acceptance")):
        if not isinstance(item, dict):
            add(findings, "ERROR", NAME, REL, 1, "CTR003", "acceptance 条目必须是对象")
            continue
        if not text(item.get("id")):
            add(findings, "ERROR", NAME, REL, 1, "CTR003", "acceptance 条目缺 id")
        testable = text(item.get("given_when_then")) or text(item.get("measure"))
        if not testable:
            add(findings, "ERROR", NAME, REL, 1, "CTR003",
                f"验收标准 {item.get('id', '?')} 不可测：需要 given_when_then 或 measure")


def check_interfaces(data, findings):
    for iface in as_list(data.get("interfaces")):
        if not isinstance(iface, dict):
            add(findings, "ERROR", NAME, REL, 1, "CTR002", "interfaces 条目必须是对象")
            continue
        name = iface.get("name", "?")
        check_fields(iface, ("name", "method", "path", "request", "response"), NAME, REL, findings, "CTR002", f"interface {name}.")
        if iface.get("method") not in METHODS:
            add(findings, "ERROR", NAME, REL, 1, "CTR002",
                f"interface {name} 的 method 不在 {sorted(METHODS)}")
        if not as_list(iface.get("errors")):
            add(findings, "ERROR", NAME, REL, 1, "CTR002",
                f"interface {name} 必须声明错误码（errors 为空）")
        if not text(iface.get("idempotent")):
            add(findings, "ERROR", NAME, REL, 1, "CTR002",
                f"interface {name} 必须声明幂等性（idempotent: yes|no:<理由>）")


def check_nfr(data, findings):
    nfr = as_dict(data.get("nfr"))
    if not nfr:
        add(findings, "ERROR", NAME, REL, 1, "CTR004", "nfr 必须是对象")
        return
    for key in NFR_KEYS:
        if not text(nfr.get(key)):
            add(findings, "ERROR", NAME, REL, 1, "CTR004",
                f"nfr 缺 {key} 的指标或验证方法")
