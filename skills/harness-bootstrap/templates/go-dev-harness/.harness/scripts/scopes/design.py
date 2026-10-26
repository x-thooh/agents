"""design: 方案证据（artifacts/design.json）：包职责、依赖无环、被否方案、失败模式。"""
from pathlib import Path

from .common import add, as_dict, as_list, check_fields, has_cycle, load_json, text, warn_example

NAME = "design"
REL = ".harness/deliverables/artifacts/design.json"


def run(ctx, findings):
    data = load_json(Path(ctx["root"]), REL, NAME, findings, "DES001")
    if not isinstance(data, dict):
        return
    warn_example(data, REL, NAME, findings, ctx["strict"])
    check_packages(data, findings)
    check_decisions(data, findings)
    check_failures(data, findings)


def check_packages(data, findings):
    graph = {}
    for pkg in as_list(data.get("packages")):
        if not isinstance(pkg, dict):
            add(findings, "ERROR", NAME, REL, 1, "DES001", "packages 条目必须是对象")
            continue
        name = pkg.get("name")
        check_fields(pkg, ("name", "responsibility"), NAME, REL, findings, "DES001", "package.")
        if not text(name):
            continue
        if name in graph:
            add(findings, "ERROR", NAME, REL, 1, "DES001", f"package {name!r} 重复声明")
        graph[name] = [d for d in as_list(pkg.get("deps")) if isinstance(d, str)]
    for name, deps in graph.items():
        for dep in deps:
            if dep not in graph:
                add(findings, "ERROR", NAME, REL, 1, "DES002",
                    f"package {name!r} 依赖未声明的包 {dep!r}")
    if has_cycle(graph):
        add(findings, "ERROR", NAME, REL, 1, "DES002", "包依赖存在环")


def check_decisions(data, findings):
    decisions = as_list(data.get("decisions"))
    if not decisions:
        add(findings, "ERROR", NAME, REL, 1, "DES003", "decisions 不能为空")
        return
    for item in decisions:
        if not isinstance(item, dict):
            add(findings, "ERROR", NAME, REL, 1, "DES003", "decisions 条目必须是对象")
            continue
        check_fields(item, ("id", "choice", "why"), NAME, REL, findings, "DES003", "decision.")
        if not as_list(item.get("rejected")):
            add(findings, "ERROR", NAME, REL, 1, "DES003",
                f"decision {item.get('id', '?')} 未记录被否方案（rejected 为空）")


def check_failures(data, findings):
    modes = as_list(data.get("failure_modes"))
    if not modes:
        add(findings, "ERROR", NAME, REL, 1, "DES004", "failure_modes 不能为空")
        return
    for mode in modes:
        if not isinstance(mode, dict):
            add(findings, "ERROR", NAME, REL, 1, "DES004", "failure_modes 条目必须是对象")
            continue
        check_fields(mode, ("mode", "detect", "mitigate"), NAME, REL, findings, "DES004", "failure_mode.")
